"""Diagnostic audit of X-48 and X-11; annotations are evaluation-only."""
import html
import json
from collections import Counter

from common import ROOT,config,read_json,sha256,write_json
from reflection_filter import iou
from render import NAMES,role_timeline


def main():
    out=ROOT/"runs/reflections-extra"
    labels=read_json(ROOT/"reflection_extra_labels.json")
    counts=read_json(out/"filter_summary.json")
    notes=read_json(out/"review_notes.json")
    outcomes=[];summary=[]
    for stat in counts:
        vid=stat["video"];src=ROOT/"runs"/vid;dst=out/vid
        decisions=read_json(dst/"decisions.json")["rows"]
        obs=read_json(src/"role_observations.json")["observations"]
        tracks={(name,stage):role_timeline(read_json(directory/f"{name}.json")["rows"],obs,config()) for name in NAMES for stage,directory in [("before",src),("after",dst)]}
        for row in [r for r in labels if r["video"]==vid]:
            entry={**row,"removed":any(r["detection_id"]==row["detection_id"] for r in decisions[row["frame"]]["removed"]),"trackers":{}}
            for name in NAMES:
                entry["trackers"][name]={}
                for stage in ["before","after"]:
                    candidates=tracks[name,stage][row["frame"]]["tracks"]
                    best=max(candidates,key=lambda t:iou(t["box"],row["box"]),default=None)
                    entry["trackers"][name][stage]={k:best[k] for k in ["id","role","det_idx"]} if best and iou(best["box"],row["box"])>=.5 else None
            outcomes.append(entry)
        selected=[r for r in outcomes if r["video"]==vid]
        direct=[r for r in selected if r["label"]=="direct"]
        reflected=[r for r in selected if r["label"]=="reflection"]
        methods={}
        for name in NAMES:
            methods[name]={}
            for stage in ["before","after"]:
                role=Counter()
                for row in direct:
                    match=row["trackers"][name][stage]
                    kind="missing" if match is None else ("unknown" if match["role"]=="unknown" else ("correct" if match["role"]==row["observable_role"] else "wrong"))
                    role[kind]+=1
                methods[name][stage]={"real_boxes_covered":sum(r["trackers"][name][stage] is not None for r in direct),"reflected_boxes_covered":sum(r["trackers"][name][stage] is not None for r in reflected),"roles_on_real_boxes":dict(role)}
        summary.append({**stat,"annotated_real_boxes":len(direct),"removed_real_boxes":sum(r["removed"] for r in direct),"annotated_reflection_boxes":len(reflected),"removed_reflection_boxes":sum(r["removed"] for r in reflected),"trackers":methods})
    evaluation={"scope":"33 candidate boxes on 12 source-selected frames; physical-person/reflection labels are assistant visual reviews. X-48 roles are explicitly confirmed by the user; X-11 roles are assistant reviews. Not exhaustive ground truth, not an independent human benchmark, not person recall or IDF1. IoU>=0.5 selects the best tracker match. No evaluation labels are inference inputs.","labels_sha256":sha256(ROOT/"reflection_extra_labels.json"),"human_role_labels_sha256":sha256(ROOT/"reflection_extra_role_labels.json"),"summary":summary,"outcomes":outcomes,"notes":notes}
    write_json(out/"evaluation.json",evaluation)
    rows=[]
    for r in summary:
        rows.append(f'<tr><td>{r["video"]}</td><td>{r["removed_real_boxes"]} / {r["annotated_real_boxes"]}</td><td>{r["removed_reflection_boxes"]} / {r["annotated_reflection_boxes"]}</td><td>{r["suppressed_detection_samples"]}</td><td>{r["model_seconds"]:.1f}</td></tr>')
    role_rows=[]
    for r in summary:
        for name in NAMES:
            before=r["trackers"][name]["before"];after=r["trackers"][name]["after"];roles=after["roles_on_real_boxes"]
            role_rows.append(f'<tr><td>{r["video"]}</td><td>{"ByteTrack" if name=="bytetrack" else "BoT-SORT + ReID"}</td><td>{before["real_boxes_covered"]} → {after["real_boxes_covered"]}</td><td>{roles.get("correct",0)}</td><td>{roles.get("wrong",0)}</td><td>{roles.get("unknown",0)}</td></tr>')
    narrative=''.join(f'<h2>{html.escape(n["video"])}</h2>'+''.join(f'<p>{html.escape(p)}</p>' for p in n["paragraphs"])+''.join(f'<p><a href="{html.escape(c["path"],quote=True)}">{html.escape(c["title"])}</a></p>' for c in n.get("evidence",[])) for n in notes)
    page='''<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>X-48 и X-11 — проверка модели</title><style>body{font:16px/1.55 system-ui;max-width:1160px;margin:30px auto;padding:0 20px;background:#f5f6f7;color:#1c2832}h1{font-size:28px}h2{font-size:21px}.note{background:#fff4dc;border-left:4px solid #b7791f;padding:12px 18px}video{width:100%;max-height:75vh;background:#15171a}select,button{font:inherit;margin:5px;padding:8px;background:white;border:1px solid #b7c1ca;border-radius:4px}table{width:100%;border-collapse:collapse;background:white}td,th{padding:10px;border-bottom:1px solid #dde2e6;text-align:left}a{color:#075e9c}.scroll{overflow:auto}</style>
<h1>Как модель справилась с X-48 и X-11</h1><p>Слева — до фильтра отражений, справа — после. На видео показаны ID и предсказанные роли; трекер можно переключить. Красные тонкие рамки справа показывают исключённые детекции для проверки. Номера ID между отдельными запусками могут различаться; ошибка — смена человека за одним ID или потеря его ID внутри одного запуска.</p>
<p class="note">Настройки, веса и запросы к моделям те же, что в первом сравнении. Роли определяются отдельно от отражений. X-48 совпадает с исходным X-5 по хешу; X-5 не входил в первый прогон. Оба новых ролика обработаны полностью.</p>
<label>Видео <select id="clip"><option>X-48</option><option>X-11</option></select></label><label>Трекер <select id="tracker"><option value="bytetrack">ByteTrack</option><option value="botsort_reid">BoT-SORT + ReID</option></select></label><button id="slow">0,5×</button><button id="normal">1×</button><a id="download" download>Скачать MP4</a><video id="video" controls playsinline preload="metadata"></video><div id="times"></div>
NARRATIVE
<h2>Сохранение людей и подавление отражений</h2><p>Проверены 12 заранее выбранных кадров: 33 рамки с уверенностью детектора ≥ 0,5. Разметка — визуальная проверка ассистентом, без независимого подтверждения человеком. В X-11 на 25 с таких рамок нет. Это проверка выбранных детекций, а не общей полноты: пропущенные детектором люди в знаменатель не входят.</p><div class="scroll"><table><tr><th>Видео</th><th>Удалено настоящих / проверено</th><th>Удалено отражений / проверено</th><th>Удалено рамок × кадров во всём видео</th><th>Генерация фильтра, с</th></tr>COUNTS</table></div><p>Время генерации фильтра исключает загрузку модели, детекцию, роли, трекеры и рендер. Это текущая реализация на L4 с эталонными ядрами модели; её скорость не представляет оптимизированный предел.</p>
<h2>Трекинг и роли на проверенных настоящих людях</h2><p>Покрытие — рамка трекера с IoU ≥ 0,5. «Верно / неверно / неизвестно» — роль после фильтра на этих же выбранных рамках. Эталон ролей X-48 <a href="role_labels_user.json">подтверждён пользователем</a>: в розовом — банкир, остальные — клиенты; для X-11 использована визуальная разметка ассистентом. Числа не относятся к уникальным людям. Другие роли, включая other, считаются неверными для размеченных участников обслуживания.</p><div class="scroll"><table><tr><th>Видео</th><th>Трекер</th><th>Покрытие до → после</th><th>Роль верна</th><th>Роль неверна</th><th>Неизвестно</th></tr>ROLES</table></div>
<p><a href="X-11-detections.jpg">Контрольные кадры: X-11</a> · <a href="X-48-detections.jpg">X-48</a> · <a href="evaluation.json">Все результаты по рамкам</a> · <a href="validation.json">Проверка выполнения</a> · <a href="../reflections/index.html">Первые четыре видео</a></p>
<p>Фильтр использует соседние наблюдения через 2 с, непрерывность предварительных ByteTrack ID, видимого настоящего партнёра и запрет удаления ID, который хотя бы раз назван настоящим человеком. Он работает офлайн и использует всю историю ролика. Эти защитные правила не гарантируют отсутствие потерь на других кадрах и камерах.</p>
<script>const clip=document.getElementById('clip'),tracker=document.getElementById('tracker'),video=document.getElementById('video');const moments={'X-48':[0,5,10,20,40,55,60,65,70],'X-11':[0,5,10,15,18,20,21,23,25]};function update(){video.src=`${clip.value}/${clip.value}-${tracker.value}-before-after.mp4`;document.getElementById('download').href=video.src;document.getElementById('times').replaceChildren();for(const t of moments[clip.value]){const b=document.createElement('button');b.textContent=t+' с';b.onclick=()=>{video.currentTime=t;video.pause()};document.getElementById('times').append(b)}}clip.onchange=update;tracker.onchange=update;document.getElementById('slow').onclick=()=>video.playbackRate=.5;document.getElementById('normal').onclick=()=>video.playbackRate=1;const initial=new URLSearchParams(location.search);if(Object.hasOwn(moments,initial.get('clip')))clip.value=initial.get('clip');if(['bytetrack','botsort_reid'].includes(initial.get('tracker')))tracker.value=initial.get('tracker');const start=Number(initial.get('t')||0);video.addEventListener('loadedmetadata',()=>{if(Number.isFinite(start)&&start>=0&&start<video.duration)video.currentTime=start},{once:true});update();</script></html>'''
    for key,value in [("NARRATIVE",narrative),("COUNTS",''.join(rows)),("ROLES",''.join(role_rows))]: page=page.replace(key,value)
    (out/"index.html").write_text(page)
    lines=["# X-48 и X-11: проверка модели","","[Открыть видео до/после](index.html)","",evaluation["scope"],""]
    for n in notes: lines.extend(["## "+n["video"],"",*n["paragraphs"],""])
    lines.extend(["## Измеренные результаты","","```json",json.dumps(summary,ensure_ascii=False,indent=2),"```",""])
    (out/"REPORT.md").write_text('\n'.join(lines))
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=="__main__": main()
