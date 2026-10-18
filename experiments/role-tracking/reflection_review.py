"""Create explicit human-review targets; these never enter inference."""
import json

from PIL import Image,ImageDraw

from common import ROOT,read_json,write_json
from prepare import frame

CASES=[
    ("R1","X-27",19,1,"Силуэт в стекле рядом с проходящей сотрудницей"),
    ("R2","X-27",21,0,"Человек в открывающейся стеклянной двери"),
    ("R3","X-27",23,1,"Верхняя короткая рамка у двери: отдельный человек или дубль?"),
    ("R4","X-38",36,2,"Белый силуэт за стеклом слева от посетителя"),
    ("R5","X-38",36,3,"Силуэт за стеклом левее предыдущей рамки"),
    ("R6","X-38",36,5,"Маленький силуэт в дальней комнате, верх кадра"),
]


def main():
    out=ROOT/"runs/reflections/review"
    out.mkdir(parents=True,exist_ok=True)
    sheet=Image.new("RGB",(960,1040),"#18212a")
    manifest=[]
    confirmed_path=ROOT/"reflection_human_labels.json"
    confirmed={r["review_id"]:r for r in read_json(confirmed_path)} if confirmed_path.exists() else {}
    for n,(key,vid,t,di,note) in enumerate(CASES):
        data=read_json(ROOT/"runs"/vid/"detections.json")
        idx=round(t*data["fps"])
        box=data["rows"][idx]["people"][di][:4]
        img=frame(ROOT/"data"/f"{vid}.mov",t)
        marked=img.copy();draw=ImageDraw.Draw(marked)
        draw.rectangle(box,outline="#ff752b",width=4)
        x,y=box[:2]
        draw.rectangle((x,max(0,y-25),x+55,max(0,y-25)+25),fill="black")
        draw.text((x+4,max(0,y-25)+3),key,fill="white",font_size=20)
        marked.save(out/f"{key}.jpg",quality=95)
        card=Image.new("RGB",(320,520),"#18212a")
        small=marked.copy();small.thumbnail((272,468))
        card.paste(small,((320-small.width)//2,34))
        d=ImageDraw.Draw(card);d.text((12,8),f"{key}  {vid}  {t}s  D{di}",fill="white",font_size=19)
        sheet.paste(card,((n%3)*320,(n//3)*520))
        manifest.append({"review_id":key,"video":vid,"frame":idx,"t":t,"detection_id":di,"box":box,"question":note,"label":None,"annotator":None,"selection":"source diagnostic cases; not independent random sample"})
        if key in confirmed:
            manifest[-1].update(label=confirmed[key]["label"],annotator=confirmed[key]["annotator"])
    sheet.save(out/"contact.jpg",quality=95)
    write_json(out/"requests.json",manifest)
    cards="".join(f'<article><h2>{m["review_id"]}: {m["video"]}, {m["t"]} с</h2><p>{m["question"]}</p><a href="{m["review_id"]}.jpg"><img src="{m["review_id"]}.jpg" alt="Рамка {m["review_id"]}, {m["video"]}, {m["t"]} с"></a><label>Метка <select data-id="{m["review_id"]}"><option value="">Не размечено</option><option value="direct">Настоящий человек</option><option value="reflection">Отражение</option><option value="duplicate">Дубль рамки того же человека</option><option value="not_person">Не человек</option><option value="uncertain">Не могу определить</option></select></label></article>' for m in manifest)
    page='''<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Проверка отражений</title><style>body{font:16px/1.5 system-ui;margin:24px;color:#172330;background:#f3f5f7}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:20px}article{background:white;padding:16px}img{width:100%;max-height:65vh;object-fit:contain}select,button{font:inherit;padding:10px}h2{font-size:20px}</style><h1>Помогите отличить отражения от настоящих людей</h1><p>Оцените только силуэт в оранжевой рамке. Настоящий человек за прозрачным стеклом — «Настоящий человек». Если рамка повторяет часть того же тела — «Дубль». Можно ответить прямо в чате: R1 — отражение, R2 — настоящий…</p><p>Метки сохраняются в этом браузере. Кнопка выгружает файл для передачи; модель не получает эти ответы автоматически.</p><button id="export">Скачать метки JSON</button><main>CARDS</main><script>const cases=MANIFEST;const key='reflection-human-review-v1';const saved=JSON.parse(localStorage.getItem(key)||'{}');for(const el of document.querySelectorAll('select')){el.value=saved[el.dataset.id]||'';el.onchange=()=>{saved[el.dataset.id]=el.value;localStorage.setItem(key,JSON.stringify(saved));}}document.getElementById('export').onclick=()=>{const labels=cases.map(x=>({...x,label:saved[x.review_id]||null,annotator:saved[x.review_id]?'human_browser':null}));const a=document.createElement('a');const url=URL.createObjectURL(new Blob([JSON.stringify(labels,null,2)],{type:'application/json'}));a.href=url;a.download='reflection-human-labels.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};</script></html>'''
    page=page.replace("saved[el.dataset.id]||''","saved[el.dataset.id]||cases.find(x=>x.review_id===el.dataset.id).label||''")
    page=page.replace("saved[x.review_id]||null","saved[x.review_id]||x.label||null")
    page=page.replace("saved[x.review_id]?'human_browser':null","saved[x.review_id]?'human_browser':x.annotator")
    (out/"index.html").write_text(page.replace("CARDS",cards).replace("MANIFEST",json.dumps(manifest,ensure_ascii=False).replace("<","\\u003c")))
    print(out/"contact.jpg")


if __name__=="__main__": main()
