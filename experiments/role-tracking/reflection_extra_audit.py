"""Prepare fixed-time detection review sheets without using model classifications."""
import cv2
from PIL import Image,ImageDraw

from common import ROOT,read_json,sampled_frames,write_json


def main():
    out=ROOT/"runs/reflections-extra"
    times=read_json(out/"audit_times.json")["videos"]
    labels=[]
    for vid,seconds in times.items():
        data=read_json(ROOT/"runs"/vid/"detections.json")
        wanted={round(t*data["fps"]) for t in seconds}
        cards=[]
        directory=out/vid/"audit"
        directory.mkdir(parents=True,exist_ok=True)
        for f,t,bgr in sampled_frames(ROOT/"data"/f"{vid}.mov",data["fps"]):
            if f not in wanted: continue
            image=Image.fromarray(cv2.cvtColor(bgr,cv2.COLOR_BGR2RGB))
            draw=ImageDraw.Draw(image)
            for i,d in enumerate(data["rows"][f]["people"]):
                if d[4]<.5: continue
                x0,y0,x1,y1=map(round,d[:4])
                draw.rectangle((x0,y0,x1,y1),outline="yellow",width=2)
                draw.rectangle((x0,max(0,y0-22),x0+90,max(0,y0-22)+22),fill="black")
                draw.text((x0+2,max(0,y0-22)),f"D{i} {d[4]:.2f}",fill="yellow",font_size=16)
                labels.append({"video":vid,"frame":f,"t":t,"detection_id":i,"box":d[:4],"label":"uncertain","annotator":"pending_assistant_review"})
            image.save(directory/f"{f:06d}.jpg",quality=95)
            card=Image.new("RGB",(image.width,image.height+36),"#17191c")
            card.paste(image,(0,36));ImageDraw.Draw(card).text((12,5),f"{vid} | {t:.1f}s",fill="white",font_size=24)
            cards.append(card)
        sheet=Image.new("RGB",(cards[0].width*3,cards[0].height*2),"white")
        for i,card in enumerate(cards): sheet.paste(card,((i%3)*card.width,(i//3)*card.height))
        sheet.save(out/f"{vid}-detections.jpg",quality=95)
    write_json(out/"audit_candidates.json",labels)


if __name__=="__main__": main()
