FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /srv
COPY pyproject.toml .
RUN pip install --no-cache-dir fastapi "uvicorn[standard]" python-multipart httpx pillow openpyxl
RUN pip install --no-cache-dir torch==2.11.0 --index-url https://download.pytorch.org/whl/cu128 \
 && pip install --no-cache-dir transformers==5.20.1
RUN python -c "from transformers import AutoImageProcessor, AutoModelForObjectDetection as M; AutoImageProcessor.from_pretrained('PekingU/rtdetr_v2_r50vd'); M.from_pretrained('PekingU/rtdetr_v2_r50vd'); from transformers import Owlv2Processor, Owlv2ForObjectDetection; Owlv2Processor.from_pretrained('google/owlv2-base-patch16-ensemble'); Owlv2ForObjectDetection.from_pretrained('google/owlv2-base-patch16-ensemble')"

COPY app app
COPY rules rules

ENV RUNS_DIR=/srv/runs HF_HUB_OFFLINE=1
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
