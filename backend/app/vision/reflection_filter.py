"""Geometry primitives for independent identity association."""
from math import hypot

def iou(a,b):
    inter=max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]))
    union=(a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-inter
    return inter/max(union,1)


def continuous(a,b,cfg):
    step=hypot((a[0]+a[2]-b[0]-b[2])/2,(a[1]+a[3]-b[1]-b[3])/2)
    size=max(hypot(a[2]-a[0],a[3]-a[1]),1)
    return iou(a,b)>=cfg["min_step_iou"] or step/size<=cfg["max_normalized_step"]

