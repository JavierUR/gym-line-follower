#!/usr/bin/env python
import numpy as np
import random
from gym_line_follower.trackcpp import collision_dect
from gym_line_follower.trackcpp import rect_p,get_rect,curve_p,get_curve
from gym_line_follower.genetic.de import diff_evolution
from gym_line_follower.genetic.fitness import curves_fitness,curves_fitness_log
import pickle

class Segment(object):
    """docstring for Segment"""
    def __init__(self, p1, p2):
        super(Segment, self).__init__()
        self.start = p1
        self.end = p2

    def get_points(self, arg):
        return []

    def points_list(self,pd):
        return self.get_points(pd).tolist()
        
class Curve(Segment):
    """docstring for Curve"""
    def __init__(self, x0,y0,cAng,da,ds):
        cAng=np.arctan2(np.sin(cAng),np.cos(cAng))
        p1 = (x0,y0,cAng)
        r=ds/da
        x,y=curve_p(x0,y0,cAng,da,r)
        ang=cAng+da
        ang=np.arctan2(np.sin(ang),np.cos(ang))
        p2 = (x,y,ang)
        super(Curve, self).__init__(p1,p2)
        self.args = [x0,y0,cAng,da,ds]
        self.da=da
        self.ds=ds
        
    def get_points(self, pd):
        return get_curve(*self.args,pd=pd)

    def __repr__(self):
        return "Curve[da:{:.2f},ds:{:.2f}]".format(*self.args[3:5])

    @classmethod
    def random_curve(cls,x0,y0,cAng,rmax,dsmax,damax,direction=None):
        rc=100+random.random()*rmax
        dac=np.clip((100+random.random()*dsmax)/rc,0,damax)
        if direction is not None:
            dac*=direction
        else:
            dac*=random.choice([-1,1])
        dsc=abs(rc*dac)
        return cls(x0,y0,cAng,dac,dsc)

class Rect(Segment):
    """docstring for Rect"""
    def __init__(self, x0,y0,cAng,ds):
        cAng=np.arctan2(np.sin(cAng),np.cos(cAng))
        p1 = (x0,y0,cAng)
        p2 = tuple(np.append(rect_p(x0,y0,cAng,ds),cAng))
        super(Rect, self).__init__(p1,p2)
        self.args = [x0,y0,cAng,ds]
        self.da=0
        self.ds=ds

    def get_points(self,pd):
        return get_rect(*self.args,pd)

    def __repr__(self):
        return "Rect[ds:{:.2f}]".format(self.args[3])  

class Track_Generator(object):
    """docstring for Track_Generator"""
    def __init__(self, ctrX, ctrY, aveRadius,bar=False):
        super(Track_Generator, self).__init__()
        self.segments = []
        self.endline = []
        self.start_finish_D=1000
        self.ctr=(ctrX,ctrY)
        self.aveRadius=aveRadius
        self.start = (ctrX + self.start_finish_D/2, ctrY + int(-aveRadius),0)
        self.bar=bar
        #self.generate_track(ctrX,ctrY,aveRadius, numVerts)
        
    @classmethod
    def generate(cls,ctrX,ctrY,aveRadius, numVerts,bar=False):
        track=cls(ctrX,ctrY,aveRadius,bar)
        track.generate_track(numVerts)
        return track

    def gen_points(self, segments,pd):
        points=[]
        for seg in segments:
            points += seg.points_list(pd)
        return points

    def get_points(self,pd):
        points=self.gen_points(self.segments,pd)
        points.insert(0,self.start[:-1])
        return points[:-1]

    def add_rect(self,x0,y0,cAng,ds):
        r=Rect(x0,y0,cAng,ds)
        if self.check_seg([r]):
            self.segments.append(r)
            return True
        else:
            return False

    def add_curve(self,x0,y0,cAng,da,ds):
        c=Curve(x0,y0,cAng,da,ds)
        if self.check_seg([c]):
            self.segments.append(c)
            return True
        else:
            return False

    def add_curve_seq(self,x0,y0,cAng,r,num,sec=0):
        da=[-np.pi,np.pi]
        ds=r*np.pi/2
        curves=[]

        curves.append(Curve(x0,y0,cAng,np.pi/2,ds))
        cX,cY,cAng=curves[-1].end

        ds=r*np.pi
        for _ in range(num):
            if sec!=0:
                curves.append(Rect(cX,cY,cAng,sec))
                cX,cY,cAng=curves[-1].end

            curves.append(Curve(cX,cY,cAng,da[0],ds))
            cX,cY,cAng=curves[-1].end

            if sec!=0:
                curves.append(Rect(cX,cY,cAng,sec))
                cX,cY,cAng=curves[-1].end

            curves.append(Curve(cX,cY,cAng,da[1],ds))
            cX,cY,cAng=curves[-1].end

        if self.check_seg(curves):
            self.segments+=curves
            return True
        else:
            return False

    def add_cross(self,x0,y0,cAng,ds1,cs1,ds2,cs2,direction=False):
        da=-np.pi/2 if direction else np.pi/2
        rect1=Rect(x0,y0,cAng,ds1)
        p1=rect1.end
        pm=rect_p(x0,y0,cAng,cs1)
        p2=np.append(rect_p(pm[0],pm[1],cAng-da,cs2),cAng+da)
        rect2=Rect(p2[0],p2[1],p2[2],ds2)
        #Random curve
        cur=Curve.random_curve(p1[0],p1[1],cAng,200,200,np.pi/2)
        pc=cur.end
        cross=[]
        cross.append(rect1)
        if not self.check_seg(cross+[rect2]):
            return False
        sol,err=self.join_points(pc,p2,[rect2]+self.endline,[rect1,cur])
        if err>50:
            return False
        p3=rect2.end
        cross.append(cur)
        cross+=sol
        cross.append(rect2)
        cAng=np.arctan2(np.sin(cAng+da),np.cos(cAng+da))
        if self.check_seg(cross):
            self.segments+=cross
            return True
        else:
            return False
        

    def join_points(self, p1, p2, preSegments=[],postSegments=[],numCurves=3):
        track=self.get_points(pd=50)
        pre=self.gen_points(preSegments,pd=50)
        post=self.gen_points(postSegments,pd=50)

        #Close curve
        ob = {"track":np.array(pre[1:-1]+track+post),
            "start":p1,
            "end":p2}
        #Boundaries of the solution [length, curvature(1/R)] where sign of curvature determines direction
        bounds=[ (200,4000), (-(1/100), (1/100))]*numCurves
        closure,fit = diff_evolution(curves_fitness,ob,bounds,
            mut=0.2,crossp=0.9,popsize=100,its=1000,stopf=1.0,bar=self.bar)
        if fit>=10000:
            print(curves_fitness_log(closure,ob))
        sol=[]
        cX,cY,cAng=p1
        for ds,cur in closure.reshape((numCurves,2)):
            da=cur*ds if np.abs(cur) >= 0.00025 else 0
            if da==0:
                sol.append(Rect(cX,cY,cAng,ds))
                cX,cY,cAng=sol[-1].end
            else:
                sol.append(Curve(cX,cY,cAng,da,ds))
                cX,cY,cAng=sol[-1].end

        pos_err=np.sqrt((cX-p2[0])**2+(cY-p2[1])**2)
        ang_err=np.abs(cAng-p2[2])
        print("=======================")
        print("Fit1: {}".format(fit))
        print("Pos error: {}".format(pos_err))
        print("Ang error: {}".format(ang_err))
        print("=======================")
        return sol,fit

    def check_seg(self, seg_list, extraSegments=[]):
        if len(self.segments)==0:
            return True
        seg=self.gen_points(seg_list,pd=50)
        track=self.get_points(pd=50)
        extra=self.gen_points(extraSegments,pd=50)
        endline=self.gen_points(self.endline, pd=50)
        seg_points=np.array(seg)
        track_points=np.array(extra+endline+track)
        #endP=seg_points[-1]
        #dist=np.max(track_points-endP,axis=1)
        if collision_dect(seg_points,track_points,th=100):
            return False
        track_points=np.append(track_points,seg_points,axis=0)
        cX,cY,cAng=seg_list[-1].end
        c1= get_curve(cX,cY,cAng,np.pi,np.pi*150,pd=50)
        if collision_dect(c1,track_points,th=100):
            c2= get_curve(cX,cY,cAng,-np.pi,np.pi*150,pd=50)
            if collision_dect(c2,track_points,th=100):
                return False
        return True
            

    def generate_track(self, numVerts):
        remVert=numVerts
        self.add_rect(self.start[0],self.start[1],self.start[2],
                                    random.randint(250,self.aveRadius-500))
        cX,cY,cAng = self.segments[-1].end
        finish = (self.ctr[0] - self.start_finish_D/2, self.ctr[1] + int(-self.aveRadius))
        #post_start=(self.ctr[0] + 500 + random.randint(250,self.aveRadius-500), self.ctr[1] + int(-self.aveRadius))
        pre_finish= (self.ctr[0] - self.start_finish_D/2 - random.randint(250,self.aveRadius-500), self.ctr[1] + int(-self.aveRadius))
        
        #End section
        self.endline=[Rect(pre_finish[0],pre_finish[1],self.start[2],finish[0]-pre_finish[0])]
        self.endline.append(Rect(finish[0],finish[1],0,self.start_finish_D))
        #points.append(post_start)

        #Primera curva
        self.segments.append(Curve.random_curve(cX,cY,cAng,500,500,np.pi,1))
        cX,cY,cAng = self.segments[-1].end
        remVert-=1

        #while remVert>0:
        lSeg=0#lSeg:0->curve lSeg:1->rect
        for _ in range(10):
            dctr=np.sqrt((cX-self.ctr[0])**2+(cY-self.ctr[1])**2)
            dactr=np.arctan2((cY-self.ctr[1]),(cX-self.ctr[0]))+np.pi-cAng
            dactr=np.arctan2(np.sin(dactr),np.cos(dactr))
            #Choose element 0->curve 1->rect 2->curve_seq 3->cross
            if lSeg:
                c=np.random.choice([0,2],1,p=[0.7,0.3])
            else:
                c=np.random.choice([0,1,2,3],1,p=[0.3,0.3,0.2,0.2])
            if c==0:
                pDa=self.segments[-1].da
                prob=0.5+(dactr/(4*np.pi))
                dirct=np.random.choice([1,-1],p=[prob,1-prob])
                damax=np.clip(np.pi-dirct*pDa,0,np.pi)
                print("damax: ",damax)
                if damax < 0.1:
                    continue
                cur=Curve.random_curve(cX,cY,cAng,500,1000,damax,dirct)
                if self.check_seg([cur]):
                    self.segments.append(cur)
                    remVert-=1
                    lSeg=0
                    print("Added Curve")
                else:
                    print("ERROR CURVE")
            elif c==1:
                if self.add_rect(cX,cY,cAng,random.randint(250,1000)):
                    remVert-=1
                    lSeg=1
                    print("Added Rect")
                else:
                    print("ERROR RECT")
            elif c==2: 
                rad=100+random.random()*100
                l=random.random()*300
                l= 0 if l<100 else l
                num=random.randint(1,3)
                if self.add_curve_seq(cX,cY,cAng,rad,num,l):
                    remVert-=(2*4+1)
                    lSeg=0
                    print("Added Curve_Seq")
                else:
                    print("ERROR SEQ")
            else:
                s1=100+random.random()*900
                s2=100+random.random()*500
                #Avoid getting stuck
                pDa=self.segments[-1].da
                if pDa > np.pi/2:
                    dirct=True
                elif pDa < -np.pi/2:
                    dirct = False
                else:
                    dirct=random.choice([True,False])
                if self.add_cross(cX,cY,cAng,s1,s1/2,s2,s2/2,direction=dirct):
                    remVert-=6
                    lSeg=1
                    print("Added Cross")
                else:
                    print("ERROR CROSS")
            cX,cY,cAng = self.segments[-1].end
        # #for i in range(numVerts-1):

        #Close curve
        closure,err=self.join_points((cX,cY,cAng),pre_finish+(0,),self.endline)
        if err > 50:
            closure,err=self.join_points((cX,cY,cAng),pre_finish+(0,),self.endline,numCurves=4)
        self.segments+=closure
        self.segments+=self.endline
        
    def get_vect(self):
        points=self.get_points(pd=5)
        c=np.array(points)
        x,y=c.T
        return x,y

    def get_length(self):
        L=0
        for s in self.segments:
            L+=s.ds
        return L/1000.0

def testTrack():
    rad=1000*3.0/2
    track=Track_Generator(0,0,rad,bar=True)
    cX,cY,cAng=track.start
    track.add_rect(cX,cY,cAng,500)
    cX,cY,cAng = track.segments[-1].end
    track.add_curve(cX,cY,cAng,np.pi,np.pi*200)
    cX,cY,cAng = track.segments[-1].end
    if track.add_curve(cX,cY,cAng,np.pi,np.pi*200):
        print("Collision test failed")
        return False
    print("Collision test passed")
    if track.add_curve(cX,cY,cAng,np.pi,np.pi*100):
        print("Continuation test failed")
        #return False
    print("Continuation test passed")
    cX,cY,cAng = track.segments[-1].end
    print(track.add_curve(cX,cY,cAng,-np.pi,(np.pi)*150))

    x,y=track.get_vect()
    plt.figure()
    plt.plot(x,y)
    plt.gca().axis('equal')
    plt.show()
    return True

if __name__ == '__main__':
    import matplotlib.pyplot as plt
    print("Test")
    rad=1000*3.0/2
    print("test passed:",testTrack())
    track=Track_Generator.generate(0,0,rad,20,bar=True)
    print(track.segments)
    x,y=track.get_vect()
    print("Length:",track.get_length(),"[m]")
    plt.figure()
    plt.plot(x,y)
    plt.gca().axis('equal')
    plt.show()
