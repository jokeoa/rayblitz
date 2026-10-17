# Промпты для синтетических видео

Назначение: проверить, что каждое правило каталога вообще срабатывает и не срабатывает на похожей сцене без нарушения, в том числе с других ракурсов. Это тестовый набор, а не обучение: пороги по нему не подбираем, AI-видео отличается от реальной камеры.

## Как генерировать

- Только text-to-video. Кадры и ролики из датасета хакатона в генераторы не загружать (FAQ 6). Image-to-video можно делать с фото вашего собственного кабинета.
- Вертикально 9:16, 8–12 секунд, без звука.
- Сохраняйте файл с именем ID, например `S01_D-09_V.mp4`, в папку `synthetic/videos/`.
- Каждая пара `_V` (нарушение) и `_N` (без нарушения) генерируется с одним ракурсом и одним кассиром: ролики должны различаться только действием.
- После генерации посмотрите ролик. Если действие не произошло или руки и деньги «плывут», ролик выбросьте. Если ролик нормальный, впишите в `synthetic/labels.csv` секунду, когда нарушение впервые хорошо видно (для `_N` оставьте пусто).
- **P1** — крупные действия, генераторы с ними справляются. **P2** — мелкие действия рук (ключ, купюра, пломба). Генераторы их часто путают, поэтому эти сцены надёжнее снять самим на телефон из угла кабинета, используя промпт как сценарий.
- Если бюджет позволяет, перегенерируйте любую пару с другим ракурсом, заменив первое предложение промпта на одно из:

  - Ракурс A: `Static CCTV footage from a camera mounted high in the upper corner of the room, looking down diagonally at the desk, the safe and the glass door.`
  - Ракурс B: `Static CCTV footage from a camera mounted high on the wall behind the cashier, looking over the cashier's shoulder towards the glass door and the client chair.`
  - Ракурс C: `Static CCTV footage from a camera on the ceiling directly above the desk, looking straight down at the desk surface, the hands and the money.`

## Промпты

### S01_D-09 — Смартфон на рабочем месте кассира (P1, ракурс A)

**S01_D-09_V** — Нарушение

```
Static CCTV footage from a camera mounted high in the upper corner of the room, looking down diagonally at the desk, the safe and the glass door. The scene is a small bank cash office with white walls, a glass door with a frosted stripe, a light wooden desk with an open laptop, a black banknote counting machine, a small banknote detector and a corded desk telephone, and a grey metal safe standing on a white stand next to the desk; a client chair stands across the desk. The cashier is a young woman in a pink cardigan. The cashier sits alone at the desk counting banknotes. At about 3 seconds she takes a smartphone out of her pocket, unlocks it and scrolls and types on it for several seconds while banknotes lie on the desk next to the counting machine. Photorealistic security camera look, natural indoor office lighting, about 10 seconds, vertical 9:16, no sound, no captions, no on-screen text, the camera does not move, no zoom.
```

**S01_D-09_N** — Без нарушения

```
Static CCTV footage from a camera mounted high in the upper corner of the room, looking down diagonally at the desk, the safe and the glass door. The scene is a small bank cash office with white walls, a glass door with a frosted stripe, a light wooden desk with an open laptop, a black banknote counting machine, a small banknote detector and a corded desk telephone, and a grey metal safe standing on a white stand next to the desk; a client chair stands across the desk. The cashier is a young woman in a pink cardigan. The cashier sits alone at the desk counting banknotes. At about 3 seconds she picks up the handset of the corded desk telephone, talks briefly, puts it back and continues working on the laptop. No smartphone is visible anywhere. Photorealistic security camera look, natural indoor office lighting, about 10 seconds, vertical 9:16, no sound, no captions, no on-screen text, the camera does not move, no zoom.
```

### S02_G-03 — Еда или напитки на рабочем месте кассира (P1, ракурс A)

**S02_G-03_V** — Нарушение

```
Static CCTV footage from a camera mounted high in the upper corner of the room, looking down diagonally at the desk, the safe and the glass door. The scene is a small bank cash office with white walls, a glass door with a frosted stripe, a light wooden desk with an open laptop, a black banknote counting machine, a small banknote detector and a corded desk telephone, and a grey metal safe standing on a white stand next to the desk; a client chair stands across the desk. The cashier is a young woman in a white blouse. The cashier counts banknotes at the desk. At about 3 seconds she opens a paper bag, eats a sandwich and drinks coffee from a paper cup right next to the stacks of banknotes and the counting machine. Photorealistic security camera look, natural indoor office lighting, about 10 seconds, vertical 9:16, no sound, no captions, no on-screen text, the camera does not move, no zoom.
```

**S02_G-03_N** — Без нарушения

```
Static CCTV footage from a camera mounted high in the upper corner of the room, looking down diagonally at the desk, the safe and the glass door. The scene is a small bank cash office with white walls, a glass door with a frosted stripe, a light wooden desk with an open laptop, a black banknote counting machine, a small banknote detector and a corded desk telephone, and a grey metal safe standing on a white stand next to the desk; a client chair stands across the desk. The cashier is a young woman in a white blouse. The cashier counts banknotes on the counting machine and puts them into the desk drawer. Nobody eats or drinks; there is no food or cup on the desk. Photorealistic security camera look, natural indoor office lighting, about 10 seconds, vertical 9:16, no sound, no captions, no on-screen text, the camera does not move, no zoom.
```

### S03_D-08 — Личные вещи на рабочем месте кассира (P1, ракурс A)

**S03_D-08_V** — Нарушение

```
Static CCTV footage from a camera mounted high in the upper corner of the room, looking down diagonally at the desk, the safe and the glass door. The scene is a small bank cash office with white walls, a glass door with a frosted stripe, a light wooden desk with an open laptop, a black banknote counting machine, a small banknote detector and a corded desk telephone, and a grey metal safe standing on a white stand next to the desk; a client chair stands across the desk. The cashier is a man in a dark shirt. The cashier enters through the glass door wearing a coat and carrying a large handbag, sits at the desk, and at about 4 seconds puts the handbag and the coat on the desk next to the counting machine, then starts counting banknotes beside them. Photorealistic security camera look, natural indoor office lighting, about 10 seconds, vertical 9:16, no sound, no captions, no on-screen text, the camera does not move, no zoom.
```

**S03_D-08_N** — Без нарушения

```
Static CCTV footage from a camera mounted high in the upper corner of the room, looking down diagonally at the desk, the safe and the glass door. The scene is a small bank cash office with white walls, a glass door with a frosted stripe, a light wooden desk with an open laptop, a black banknote counting machine, a small banknote detector and a corded desk telephone, and a grey metal safe standing on a white stand next to the desk; a client chair stands across the desk. The cashier is a man in a dark shirt. The cashier enters through the glass door without a coat or bag, sits at the desk and starts counting banknotes. The desk holds only the laptop, the counting machine and the telephone. Photorealistic security camera look, natural indoor office lighting, about 10 seconds, vertical 9:16, no sound, no captions, no on-screen text, the camera does not move, no zoom.
```

### S04_D-01 — Наличные или ценности без присмотра (P1, ракурс A)

**S04_D-01_V** — Нарушение

```
Static CCTV footage from a camera mounted high in the upper corner of the room, looking down diagonally at the desk, the safe and the glass door. The scene is a small bank cash office with white walls, a glass door with a frosted stripe, a light wooden desk with an open laptop, a black banknote counting machine, a small banknote detector and a corded desk telephone, and a grey metal safe standing on a white stand next to the desk; a client chair stands across the desk. The cashier is a young woman in a pink cardigan. The cashier counts a stack of banknotes, leaves the stack lying on the open desk, stands up at about 4 seconds and walks out through the glass door. The banknotes remain on the desk in the empty room. Photorealistic security camera look, natural indoor office lighting, about 10 seconds, vertical 9:16, no sound, no captions, no on-screen text, the camera does not move, no zoom.
```

**S04_D-01_N** — Без нарушения

```
Static CCTV footage from a camera mounted high in the upper corner of the room, looking down diagonally at the desk, the safe and the glass door. The scene is a small bank cash office with white walls, a glass door with a frosted stripe, a light wooden desk with an open laptop, a black banknote counting machine, a small banknote detector and a corded desk telephone, and a grey metal safe standing on a white stand next to the desk; a client chair stands across the desk. The cashier is a young woman in a pink cardigan. The cashier counts a stack of banknotes, puts it into the grey safe, closes the safe door, stands up and walks out through the glass door. The desk is empty. Photorealistic security camera look, natural indoor office lighting, about 10 seconds, vertical 9:16, no sound, no captions, no on-screen text, the camera does not move, no zoom.
```

### S05_D-02 — Сейф открыт без необходимости (P1, ракурс B)

**S05_D-02_V** — Нарушение

```
Static CCTV footage from a camera mounted high on the wall behind the cashier, looking over the cashier's shoulder towards the glass door and the client chair. The scene is a small bank cash office with white walls, a glass door with a frosted stripe, a light wooden desk with an open laptop, a black banknote counting machine, a small banknote detector and a corded desk telephone, and a grey metal safe standing on a white stand next to the desk; a client chair stands across the desk. The cashier is a young woman in a white blouse. The grey safe next to the desk stands with its door wide open, banknote bundles visible inside, for the whole clip, while the cashier sits at the laptop typing and never touches the safe. Photorealistic security camera look, natural indoor office lighting, about 10 seconds, vertical 9:16, no sound, no captions, no on-screen text, the camera does not move, no zoom.
```

**S05_D-02_N** — Без нарушения

```
Static CCTV footage from a camera mounted high on the wall behind the cashier, looking over the cashier's shoulder towards the glass door and the client chair. The scene is a small bank cash office with white walls, a glass door with a frosted stripe, a light wooden desk with an open laptop, a black banknote counting machine, a small banknote detector and a corded desk telephone, and a grey metal safe standing on a white stand next to the desk; a client chair stands across the desk. The cashier is a young woman in a white blouse. The cashier opens the grey safe, takes out one bundle of banknotes, closes the safe door right away and goes back to typing on the laptop. Photorealistic security camera look, natural indoor office lighting, about 10 seconds, vertical 9:16, no sound, no captions, no on-screen text, the camera does not move, no zoom.
```

### S06_A-01 — Рабочая станция не заблокирована при уходе (P1, ракурс A)

**S06_A-01_V** — Нарушение

```
Static CCTV footage from a camera mounted high in the upper corner of the room, looking down diagonally at the desk, the safe and the glass door. The scene is a small bank cash office with white walls, a glass door with a frosted stripe, a light wooden desk with an open laptop, a black banknote counting machine, a small banknote detector and a corded desk telephone, and a grey metal safe standing on a white stand next to the desk; a client chair stands across the desk. The cashier is a man in a dark shirt. The cashier works on the laptop, which shows a bright spreadsheet window. At about 3 seconds he stands up and leaves the room through the glass door. The laptop stays open with the bright working window on the screen. Photorealistic security camera look, natural indoor office lighting, about 10 seconds, vertical 9:16, no sound, no captions, no on-screen text, the camera does not move, no zoom.
```

**S06_A-01_N** — Без нарушения

```
Static CCTV footage from a camera mounted high in the upper corner of the room, looking down diagonally at the desk, the safe and the glass door. The scene is a small bank cash office with white walls, a glass door with a frosted stripe, a light wooden desk with an open laptop, a black banknote counting machine, a small banknote detector and a corded desk telephone, and a grey metal safe standing on a white stand next to the desk; a client chair stands across the desk. The cashier is a man in a dark shirt. The cashier works on the laptop, presses keys so the screen changes to a dark lock screen with a large clock, then stands up and leaves the room through the glass door. Photorealistic security camera look, natural indoor office lighting, about 10 seconds, vertical 9:16, no sound, no captions, no on-screen text, the camera does not move, no zoom.
```

### S07_A-04 — Документы и печати оставлены на столе (P1, ракурс A)

**S07_A-04_V** — Нарушение

```
Static CCTV footage from a camera mounted high in the upper corner of the room, looking down diagonally at the desk, the safe and the glass door. The scene is a small bank cash office with white walls, a glass door with a frosted stripe, a light wooden desk with an open laptop, a black banknote counting machine, a small banknote detector and a corded desk telephone, and a grey metal safe standing on a white stand next to the desk; a client chair stands across the desk. The cashier is a young woman in a pink cardigan. Client paper documents, an open folder and two rubber bank stamps lie spread out on the desk. At about 3 seconds the cashier stands up and leaves the room, leaving all of them on the desk. Photorealistic security camera look, natural indoor office lighting, about 10 seconds, vertical 9:16, no sound, no captions, no on-screen text, the camera does not move, no zoom.
```

**S07_A-04_N** — Без нарушения

```
Static CCTV footage from a camera mounted high in the upper corner of the room, looking down diagonally at the desk, the safe and the glass door. The scene is a small bank cash office with white walls, a glass door with a frosted stripe, a light wooden desk with an open laptop, a black banknote counting machine, a small banknote detector and a corded desk telephone, and a grey metal safe standing on a white stand next to the desk; a client chair stands across the desk. The cashier is a young woman in a pink cardigan. The cashier gathers the papers into a folder, puts the folder and the two rubber stamps into the desk drawer, closes it, stands up and leaves the room. Photorealistic security camera look, natural indoor office lighting, about 10 seconds, vertical 9:16, no sound, no captions, no on-screen text, the camera does not move, no zoom.
```

### S08_D-12 — Посторонний в помещении с ценностями (P1, ракурс B)

**S08_D-12_V** — Нарушение

```
Static CCTV footage from a camera mounted high on the wall behind the cashier, looking over the cashier's shoulder towards the glass door and the client chair. The scene is a small bank cash office with white walls, a glass door with a frosted stripe, a light wooden desk with an open laptop, a black banknote counting machine, a small banknote detector and a corded desk telephone, and a grey metal safe standing on a white stand next to the desk; a client chair stands across the desk. The cashier is a young woman in a white blouse. The cashier sits at the desk with her back to the glass door, counting banknotes. At about 3 seconds a man in a dark jacket opens the door, walks in unnoticed, comes around to the cashier's side of the desk and stands next to the counting machine and the safe. Photorealistic security camera look, natural indoor office lighting, about 10 seconds, vertical 9:16, no sound, no captions, no on-screen text, the camera does not move, no zoom.
```

**S08_D-12_N** — Без нарушения

```
Static CCTV footage from a camera mounted high on the wall behind the cashier, looking over the cashier's shoulder towards the glass door and the client chair. The scene is a small bank cash office with white walls, a glass door with a frosted stripe, a light wooden desk with an open laptop, a black banknote counting machine, a small banknote detector and a corded desk telephone, and a grey metal safe standing on a white stand next to the desk; a client chair stands across the desk. The cashier is a young woman in a white blouse. A client opens the glass door, walks in, sits on the client chair across the desk from the cashier and hands over a document. Nobody comes to the cashier's side of the desk. Photorealistic security camera look, natural indoor office lighting, about 10 seconds, vertical 9:16, no sound, no captions, no on-screen text, the camera does not move, no zoom.
```

### S09_D-13 — Дверь кассы оставлена открытой (P1, ракурс B)

**S09_D-13_V** — Нарушение

```
Static CCTV footage from a camera mounted high on the wall behind the cashier, looking over the cashier's shoulder towards the glass door and the client chair. The scene is a small bank cash office with white walls, a glass door with a frosted stripe, a light wooden desk with an open laptop, a black banknote counting machine, a small banknote detector and a corded desk telephone, and a grey metal safe standing on a white stand next to the desk; a client chair stands across the desk. The cashier is a man in a dark shirt. The cashier enters through the glass door, leaves the door wide open behind him, sits at the desk with his back to the open door, switches on the counting machine and the laptop and starts working. The door stays open for the whole clip. Photorealistic security camera look, natural indoor office lighting, about 10 seconds, vertical 9:16, no sound, no captions, no on-screen text, the camera does not move, no zoom.
```

**S09_D-13_N** — Без нарушения

```
Static CCTV footage from a camera mounted high on the wall behind the cashier, looking over the cashier's shoulder towards the glass door and the client chair. The scene is a small bank cash office with white walls, a glass door with a frosted stripe, a light wooden desk with an open laptop, a black banknote counting machine, a small banknote detector and a corded desk telephone, and a grey metal safe standing on a white stand next to the desk; a client chair stands across the desk. The cashier is a man in a dark shirt. The cashier enters through the glass door, closes it behind him, sits at the desk and switches on the counting machine and the laptop. The door stays closed. Photorealistic security camera look, natural indoor office lighting, about 10 seconds, vertical 9:16, no sound, no captions, no on-screen text, the camera does not move, no zoom.
```

### S10_B-02 — Кассовая операция без предъявления удостоверения (P1, ракурс A)

**S10_B-02_V** — Нарушение

```
Static CCTV footage from a camera mounted high in the upper corner of the room, looking down diagonally at the desk, the safe and the glass door. The scene is a small bank cash office with white walls, a glass door with a frosted stripe, a light wooden desk with an open laptop, a black banknote counting machine, a small banknote detector and a corded desk telephone, and a grey metal safe standing on a white stand next to the desk; a client chair stands across the desk. The cashier is a young woman in a pink cardigan. A client sits across the desk and puts a stack of banknotes on the desk. The cashier immediately takes the money and puts it into the counting machine. The client never shows or hands over any identity card. Photorealistic security camera look, natural indoor office lighting, about 10 seconds, vertical 9:16, no sound, no captions, no on-screen text, the camera does not move, no zoom.
```

**S10_B-02_N** — Без нарушения

```
Static CCTV footage from a camera mounted high in the upper corner of the room, looking down diagonally at the desk, the safe and the glass door. The scene is a small bank cash office with white walls, a glass door with a frosted stripe, a light wooden desk with an open laptop, a black banknote counting machine, a small banknote detector and a corded desk telephone, and a grey metal safe standing on a white stand next to the desk; a client chair stands across the desk. The cashier is a young woman in a pink cardigan. A client sits across the desk and first hands the cashier a plastic ID card. The cashier looks at the card and at the client's face, returns the card, then takes the client's banknotes and puts them into the counting machine. Photorealistic security camera look, natural indoor office lighting, about 10 seconds, vertical 9:16, no sound, no captions, no on-screen text, the camera does not move, no zoom.
```

### S11_B-04 — Наличные выданы не тому, кто прошёл идентификацию (P2, ракурс A)

**S11_B-04_V** — Нарушение

```
Static CCTV footage from a camera mounted high in the upper corner of the room, looking down diagonally at the desk, the safe and the glass door. The scene is a small bank cash office with white walls, a glass door with a frosted stripe, a light wooden desk with an open laptop, a black banknote counting machine, a small banknote detector and a corded desk telephone, and a grey metal safe standing on a white stand next to the desk; a client chair stands across the desk. The cashier is a young woman in a white blouse. A first client shows an ID card and the cashier prepares a stack of banknotes on the desk. The first client stands up and leaves. A second, different client comes in, sits down, and the cashier hands him the prepared banknotes without asking for any document. Photorealistic security camera look, natural indoor office lighting, about 10 seconds, vertical 9:16, no sound, no captions, no on-screen text, the camera does not move, no zoom.
```

**S11_B-04_N** — Без нарушения

```
Static CCTV footage from a camera mounted high in the upper corner of the room, looking down diagonally at the desk, the safe and the glass door. The scene is a small bank cash office with white walls, a glass door with a frosted stripe, a light wooden desk with an open laptop, a black banknote counting machine, a small banknote detector and a corded desk telephone, and a grey metal safe standing on a white stand next to the desk; a client chair stands across the desk. The cashier is a young woman in a white blouse. A first client shows an ID card, receives the banknotes and leaves. A second, different client comes in, sits down and first hands the cashier his own ID card; the cashier checks it before doing anything else. Photorealistic security camera look, natural indoor office lighting, about 10 seconds, vertical 9:16, no sound, no captions, no on-screen text, the camera does not move, no zoom.
```

### S12_D-04 — Приём и пересчёт денег не в присутствии клиента (P2, ракурс A)

**S12_D-04_V** — Нарушение

```
Static CCTV footage from a camera mounted high in the upper corner of the room, looking down diagonally at the desk, the safe and the glass door. The scene is a small bank cash office with white walls, a glass door with a frosted stripe, a light wooden desk with an open laptop, a black banknote counting machine, a small banknote detector and a corded desk telephone, and a grey metal safe standing on a white stand next to the desk; a client chair stands across the desk. The cashier is a man in a dark shirt. A client hands a stack of banknotes to the cashier, then stands up and leaves the room. Only after the client has gone does the cashier put the banknotes into the counting machine and count them. Photorealistic security camera look, natural indoor office lighting, about 10 seconds, vertical 9:16, no sound, no captions, no on-screen text, the camera does not move, no zoom.
```

**S12_D-04_N** — Без нарушения

```
Static CCTV footage from a camera mounted high in the upper corner of the room, looking down diagonally at the desk, the safe and the glass door. The scene is a small bank cash office with white walls, a glass door with a frosted stripe, a light wooden desk with an open laptop, a black banknote counting machine, a small banknote detector and a corded desk telephone, and a grey metal safe standing on a white stand next to the desk; a client chair stands across the desk. The cashier is a man in a dark shirt. A client hands a stack of banknotes to the cashier and stays seated while the cashier counts them on the counting machine. Then the client leaves. Photorealistic security camera look, natural indoor office lighting, about 10 seconds, vertical 9:16, no sound, no captions, no on-screen text, the camera does not move, no zoom.
```

### S13_D-05 — Выдача наличных без пересчёта при клиенте (P2, ракурс C)

**S13_D-05_V** — Нарушение

```
Static CCTV footage from a camera on the ceiling directly above the desk, looking straight down at the desk surface, the hands and the money. The scene is a small bank cash office with white walls, a glass door with a frosted stripe, a light wooden desk with an open laptop, a black banknote counting machine, a small banknote detector and a corded desk telephone, and a grey metal safe standing on a white stand next to the desk; a client chair stands across the desk. The cashier is a young woman in a pink cardigan. The cashier takes a thick stack of banknotes from the counting machine, pulls out part of the stack by hand without counting it and hands it straight to the client across the desk, who puts it into his pocket at once. Photorealistic security camera look, natural indoor office lighting, about 10 seconds, vertical 9:16, no sound, no captions, no on-screen text, the camera does not move, no zoom.
```

**S13_D-05_N** — Без нарушения

```
Static CCTV footage from a camera on the ceiling directly above the desk, looking straight down at the desk surface, the hands and the money. The scene is a small bank cash office with white walls, a glass door with a frosted stripe, a light wooden desk with an open laptop, a black banknote counting machine, a small banknote detector and a corded desk telephone, and a grey metal safe standing on a white stand next to the desk; a client chair stands across the desk. The cashier is a young woman in a pink cardigan. The cashier puts the banknotes into the counting machine, the machine counts them in front of the client, the cashier hands over the counted stack and the client counts the notes at the desk. Photorealistic security camera look, natural indoor office lighting, about 10 seconds, vertical 9:16, no sound, no captions, no on-screen text, the camera does not move, no zoom.
```

### S14_D-06 — Пересчёт без счётной машины (P2, ракурс C)

**S14_D-06_V** — Нарушение

```
Static CCTV footage from a camera on the ceiling directly above the desk, looking straight down at the desk surface, the hands and the money. The scene is a small bank cash office with white walls, a glass door with a frosted stripe, a light wooden desk with an open laptop, a black banknote counting machine, a small banknote detector and a corded desk telephone, and a grey metal safe standing on a white stand next to the desk; a client chair stands across the desk. The cashier is a young woman in a white blouse. The cashier counts a thick stack of banknotes only by hand, note by note, and wraps it with a paper band, while the banknote counting machine stands switched off next to her. Photorealistic security camera look, natural indoor office lighting, about 10 seconds, vertical 9:16, no sound, no captions, no on-screen text, the camera does not move, no zoom.
```

**S14_D-06_N** — Без нарушения

```
Static CCTV footage from a camera on the ceiling directly above the desk, looking straight down at the desk surface, the hands and the money. The scene is a small bank cash office with white walls, a glass door with a frosted stripe, a light wooden desk with an open laptop, a black banknote counting machine, a small banknote detector and a corded desk telephone, and a grey metal safe standing on a white stand next to the desk; a client chair stands across the desk. The cashier is a young woman in a white blouse. The cashier puts a stack of banknotes into the counting machine, the machine counts them, and then the cashier wraps the stack with a paper band. Photorealistic security camera look, natural indoor office lighting, about 10 seconds, vertical 9:16, no sound, no captions, no on-screen text, the camera does not move, no zoom.
```

### S15_D-18 — Отбракованная машиной купюра добавлена в пачку (P2, ракурс C)

**S15_D-18_V** — Нарушение

```
Static CCTV footage from a camera on the ceiling directly above the desk, looking straight down at the desk surface, the hands and the money. The scene is a small bank cash office with white walls, a glass door with a frosted stripe, a light wooden desk with an open laptop, a black banknote counting machine, a small banknote detector and a corded desk telephone, and a grey metal safe standing on a white stand next to the desk; a client chair stands across the desk. The cashier is a man in a dark shirt. The cashier runs banknotes through the counting machine. The machine stops and pushes one banknote out into the reject pocket. The cashier takes that rejected banknote and puts it on top of the counted stack without checking it. Photorealistic security camera look, natural indoor office lighting, about 10 seconds, vertical 9:16, no sound, no captions, no on-screen text, the camera does not move, no zoom.
```

**S15_D-18_N** — Без нарушения

```
Static CCTV footage from a camera on the ceiling directly above the desk, looking straight down at the desk surface, the hands and the money. The scene is a small bank cash office with white walls, a glass door with a frosted stripe, a light wooden desk with an open laptop, a black banknote counting machine, a small banknote detector and a corded desk telephone, and a grey metal safe standing on a white stand next to the desk; a client chair stands across the desk. The cashier is a man in a dark shirt. The cashier runs banknotes through the counting machine. The machine pushes one banknote out into the reject pocket. The cashier puts the rejected banknote aside on the desk and checks it under the banknote detector. Photorealistic security camera look, natural indoor office lighting, about 10 seconds, vertical 9:16, no sound, no captions, no on-screen text, the camera does not move, no zoom.
```

### S16_D-11 — Сумка с ценностями принята без проверки (P2, ракурс A)

**S16_D-11_V** — Нарушение

```
Static CCTV footage from a camera mounted high in the upper corner of the room, looking down diagonally at the desk, the safe and the glass door. The scene is a small bank cash office with white walls, a glass door with a frosted stripe, a light wooden desk with an open laptop, a black banknote counting machine, a small banknote detector and a corded desk telephone, and a grey metal safe standing on a white stand next to the desk; a client chair stands across the desk. The cashier is a young woman in a pink cardigan. A courier in a dark uniform enters through the glass door with a sealed green cash bag, hands it to the cashier and immediately leaves. The cashier puts the bag straight into the safe without looking at the seal. Photorealistic security camera look, natural indoor office lighting, about 10 seconds, vertical 9:16, no sound, no captions, no on-screen text, the camera does not move, no zoom.
```

**S16_D-11_N** — Без нарушения

```
Static CCTV footage from a camera mounted high in the upper corner of the room, looking down diagonally at the desk, the safe and the glass door. The scene is a small bank cash office with white walls, a glass door with a frosted stripe, a light wooden desk with an open laptop, a black banknote counting machine, a small banknote detector and a corded desk telephone, and a grey metal safe standing on a white stand next to the desk; a client chair stands across the desk. The cashier is a young woman in a pink cardigan. A courier hands a sealed green cash bag to the cashier and waits. The cashier turns the bag in her hands, inspects the seal and the label, signs a paper document and gives it to the courier, who then leaves. Photorealistic security camera look, natural indoor office lighting, about 10 seconds, vertical 9:16, no sound, no captions, no on-screen text, the camera does not move, no zoom.
```

### S17_D-03 — Ключ оставлен в замке сейфа (P2, ракурс A)

**S17_D-03_V** — Нарушение

```
Static CCTV footage from a camera mounted high in the upper corner of the room, looking down diagonally at the desk, the safe and the glass door. The scene is a small bank cash office with white walls, a glass door with a frosted stripe, a light wooden desk with an open laptop, a black banknote counting machine, a small banknote detector and a corded desk telephone, and a grey metal safe standing on a white stand next to the desk; a client chair stands across the desk. The cashier is a young woman in a white blouse. The cashier closes the grey safe door with a key, leaves the key sticking out of the safe lock with a key tag hanging from it, stands up and walks out through the glass door. Photorealistic security camera look, natural indoor office lighting, about 10 seconds, vertical 9:16, no sound, no captions, no on-screen text, the camera does not move, no zoom.
```

**S17_D-03_N** — Без нарушения

```
Static CCTV footage from a camera mounted high in the upper corner of the room, looking down diagonally at the desk, the safe and the glass door. The scene is a small bank cash office with white walls, a glass door with a frosted stripe, a light wooden desk with an open laptop, a black banknote counting machine, a small banknote detector and a corded desk telephone, and a grey metal safe standing on a white stand next to the desk; a client chair stands across the desk. The cashier is a young woman in a white blouse. The cashier closes the grey safe door with a key, pulls the key out, puts it into her pocket and walks out through the glass door. Photorealistic security camera look, natural indoor office lighting, about 10 seconds, vertical 9:16, no sound, no captions, no on-screen text, the camera does not move, no zoom.
```

### S18_D-10 — Деньги убраны в карман, одежду или сумку (P2, ракурс C)

**S18_D-10_V** — Нарушение

```
Static CCTV footage from a camera on the ceiling directly above the desk, looking straight down at the desk surface, the hands and the money. The scene is a small bank cash office with white walls, a glass door with a frosted stripe, a light wooden desk with an open laptop, a black banknote counting machine, a small banknote detector and a corded desk telephone, and a grey metal safe standing on a white stand next to the desk; a client chair stands across the desk. The cashier is a man in a dark shirt. The cashier counts banknotes at the desk, glances at the door, then slips one banknote into his pocket and continues counting. Photorealistic security camera look, natural indoor office lighting, about 10 seconds, vertical 9:16, no sound, no captions, no on-screen text, the camera does not move, no zoom.
```

**S18_D-10_N** — Без нарушения

```
Static CCTV footage from a camera on the ceiling directly above the desk, looking straight down at the desk surface, the hands and the money. The scene is a small bank cash office with white walls, a glass door with a frosted stripe, a light wooden desk with an open laptop, a black banknote counting machine, a small banknote detector and a corded desk telephone, and a grey metal safe standing on a white stand next to the desk; a client chair stands across the desk. The cashier is a man in a dark shirt. The cashier counts banknotes at the desk and puts all of them into the counting machine tray and then into the desk drawer. Photorealistic security camera look, natural indoor office lighting, about 10 seconds, vertical 9:16, no sound, no captions, no on-screen text, the camera does not move, no zoom.
```
