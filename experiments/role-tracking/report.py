"""Build a local, self-contained review page referencing the rendered MP4 files."""
import json

from common import ROOT, config, read_json


def main():
    cfg=config()
    summary=read_json(ROOT/"runs/summary.json")
    cases=read_json(ROOT/"audit_cases.json")
    rows="".join(
        f"<tr><td>{r['video']}</td><td>{'ByteTrack' if r['tracker']=='bytetrack' else 'BoT-SORT + ReID'}</td><td>{r['track_count']}</td><td>{r['steady_update_ms_median']:.2f}</td><td>{r['steady_update_ms_p95']:.2f}</td><td>{100*r['role_coverage']:.1f}%</td></tr>"
        for r in summary
    )
    options="".join(f'<option value="{v}">{v}</option>' for v in cfg["videos"])
    cases_json=json.dumps(cases,ensure_ascii=False).replace("<","\\u003c")
    page='''<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Проверка ID и ролей — ByteTrack / BoT-SORT</title>
<style>
:root{font-family:system-ui,sans-serif;color:#1c2832;background:#f5f6f7}body{max-width:1160px;margin:32px auto;padding:0 20px;line-height:1.55}h1{font-size:28px;line-height:1.2}h2{font-size:20px;margin-top:32px}p{max-width:950px}.note{border-left:4px solid #b7791f;padding:12px 18px;background:#fff8e7}select,button{font:inherit;padding:8px 12px;border:1px solid #b7c1ca;border-radius:5px;background:white;cursor:pointer;margin:4px}video{display:block;width:100%;max-height:75vh;background:#15171a;margin-top:14px}table{border-collapse:collapse;width:100%;background:white}td,th{padding:10px;text-align:left;border-bottom:1px solid #dde2e6}th{font-weight:600}a{color:#075e9c}.moment{display:inline-block}.controls{display:flex;gap:12px;flex-wrap:wrap;align-items:center}.small{font-size:14px;color:#51616e}code{font-family:ui-monospace,monospace}img{max-width:100%}.tablewrap{overflow:auto}
</style>
<h1>ByteTrack и BoT-SORT + ReID на четырёх видео</h1>
<p>Одинаковые детекции RT-DETRv2, 10 кадров/с, исходное разрешение. Слева ByteTrack, справа BoT-SORT с OSNet ReID. Роли: общие автоматические наблюдения Qwen3.5-9B с подтверждением во времени.</p>
<p class="note">Это исследовательский прогон. Роли на видео — предсказания. Число ID, покрытие ролями и совпадение рамок не являются точностью. Независимой разметки траекторий и ролей пока нет.</p>
<div class="controls"><label>Видео <select id="clip">OPTIONS</select></label><button id="normal">Скорость 1×</button><button id="slow">Скорость 0,5×</button><a id="download" download>Скачать MP4</a></div>
<video id="video" controls preload="metadata" playsinline></video>
<p class="small">Зелёный — banker; синий — customer; серый — other; жёлтый — unknown. «overlap?» означает пересечение рамок, которое само по себе не доказывает физическое перекрытие.</p>
<h2>Моменты для проверки</h2><div id="moments"></div>
<h2>Отражения становятся отдельными людьми</h2>
<p>X-4, 15 с: отражение сотрудницы слева получает score 0,889, сама сотрудница — 0,879. На 20 с два отражения получают 0,772 и 0,657. Это оценки детектора, не вероятность реального присутствия. Один порог score не отделяет отражение от человека даже в проверенном кадре 15 с. Оба трекера получают эти ложные детекции.</p>
<p>Исключить всё стекло тоже нельзя: в X-27 сотрудница проходит через стеклянную дверь. Нужна отдельная проверка «реальный человек / отражение / неоднозначно» с контролем пропусков настоящих входов и выходов. Такой фильтр в текущем прогоне отсутствует.</p>
<p><a href="X-4/role_frames/000150.jpg">Исходные рамки X-4, 15 с</a> · <a href="audit/X-27-exit_through_glass_door.jpg">Настоящий выход через стеклянную дверь</a></p>
<h2>Найденный сбой после перекрытия</h2>
<p>X-18: сотрудница встаёт перед сидящим посетителем, появляются дубли рамок. На выходе из перекрытия, в 13,6–13,7 с, ByteTrack присваивает основной рамке посетителя ID 12, BoT-SORT — ID 11. В 13,8 с ByteTrack возвращает исходный ID 4; BoT-SORT сохраняет ID 11 до конца ролика. Короткий сбой есть у обоих методов. Разница — в восстановлении прежней связи.</p>
<p><a href="audit/X-18-occlusion_detail.jpg">Открыть покадровое сравнение</a> · <a href="REPORT.md">Подробный разбор и ограничения</a></p>
<h2>Стабильный ID не гарантирует правильную роль</h2>
<p>На X-4 в 15–30 с и 65–70 с оба варианта называют сотрудницу клиентом, а посетителя банкиром. Их ID при этом стабильны. Повторные согласованные ответы Qwen закрепляют ошибку роли или привязки ответа к рамке. Улучшение трекинга само по себе этот сбой не устраняет.</p>
<p><a href="audit/X-4-role_inversion.jpg">Посмотреть инверсию ролей</a></p>
<h2>Стоимость и диагностические счётчики</h2>
<div class="tablewrap"><table><thead><tr><th>Видео</th><th>Трекер</th><th>Выдано ID</th><th>Медиана, мс/кадр</th><th>p95, мс/кадр</th><th>Есть роль</th></tr></thead><tbody>ROWS</tbody></table></div>
<p class="small">Время относится только к tracker.update после первого кадра, включает извлечение ReID-признаков для BoT-SORT. Детекция, Qwen, декодирование и создание видео сюда не входят. «Есть роль» — доля видимых отсчётов треков с ответом кроме unknown, включая ложные и фоновые треки; это не точность. Меньшее число ID может означать как меньше разрывов, так и больше ошибочных объединений.</p>
<p class="small">Полные данные: <a href="summary.json">сводка</a>, <a href="environment.json">окружение</a>, <a href="run.json">этапы запуска</a>, <a href="pip-freeze.txt">версии пакетов</a>.</p>
<script>
const cases=CASES;
const clip=document.getElementById('clip'),video=document.getElementById('video'),moments=document.getElementById('moments');
function selectClip(){const name=clip.value;video.src=`${name}/${name}-comparison.mp4`;document.getElementById('download').href=video.src;moments.replaceChildren();for(const c of cases.filter(x=>x.video===name)){const p=document.createElement('p');const title=document.createElement('strong');title.textContent=c.name+' ';p.append(title);for(const t of c.times){const b=document.createElement('button');b.textContent=t+' с';b.addEventListener('click',()=>{video.currentTime=t;video.pause()});p.append(b)}moments.append(p)}}
clip.addEventListener('change',selectClip);document.getElementById('normal').addEventListener('click',()=>video.playbackRate=1);document.getElementById('slow').addEventListener('click',()=>video.playbackRate=.5);selectClip();
</script></html>'''
    page=page.replace("OPTIONS",options).replace("ROWS",rows).replace("CASES",cases_json)
    path=ROOT/"runs/index.html"
    path.write_text(page)
    print(path)


if __name__=="__main__":
    main()
