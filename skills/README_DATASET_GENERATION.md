# Skill Dataset Generator

## Overview

이 스크립트는 `skills/MDs/` 디렉토리에 있는 스킬 마크다운 파일들을 읽어들이고, **Google Gemini API**를 사용하여 가상의 유저 쿼리와 해당 함수 호출 데이터를 자동으로 생성합니다. 생성된 데이터셋은 `NaturalInstructionsTaskDataset` 과 호환되는 형식으로 저장됩니다.

> **RPM 절약 — 배치 요청**
> Gemini 무료 티어 (그리고 대부분의 유료 플랜) 는 RPM (분당 요청 수) 으로 quota 를 잰다. 본 스크립트는 한 번의 Gemini 요청에 **여러 스킬을 묶어서** 전송하고, 응답을 스킬별로 파싱해 한 번에 저장한다. `--batch_size` 로 한 요청에 묶을 스킬 수를 조절한다.

## 사용법

### 기본 사용법

```bash
# GEMINI_API_KEY 환경 변수 설정 (또는 GOOGLE_API_KEY)
export GEMINI_API_KEY="your-api-key-here"

# 모든 스킬 파일에 대해 데이터셋 생성
# (기본값: 스킬 당 5 개 샘플, 한 요청에 5 개 스킬 묶음)
python skills/generate_skill_dataset.py
```

PowerShell 의 경우:

```powershell
$env:GEMINI_API_KEY = "your-api-key-here"
python skills/generate_skill_dataset.py
```

### 옵션

```
usage: generate_skill_dataset.py [-h] [--skills_dir SKILLS_DIR]
                                 [--output_dir OUTPUT_DIR]
                                 [--output_file OUTPUT_FILE]
                                 [--num_samples NUM_SAMPLES]
                                 [--batch_size BATCH_SIZE]
                                 [--api_key API_KEY]
                                 [--model MODEL]
                                 [--skills [SKILLS ...]]
                                 [--resume]

options:
  --skills_dir          스킬 마크다운 파일이 있는 디렉토리 (기본값: skills/MDs)
  --output_dir          생성된 데이터셋을 저장할 디렉토리 (기본값: skills/generated_datasets)
  --output_file         출력 파일명 (기본값: train_data.json)
  --num_samples         스킬 당 생성할 샘플 수 (기본값: 5)
  --batch_size          한 번의 Gemini 요청에 묶을 스킬 수 (기본값: 5).
                        값이 클수록 요청 수는 줄어들지만 프롬프트 / 응답이 커진다.
  --api_key             Gemini API 키 (환경 변수 GEMINI_API_KEY / GOOGLE_API_KEY 도 사용 가능)
  --model               사용할 Gemini 모델 (기본값: gemini-2.0-flash).
                        예: gemini-2.0-flash, gemini-1.5-flash, gemini-2.0-pro
  --skills              처리할 특정 스킬 파일들 (기본값: 모든 .md 파일)
  --resume              기존 데이터셋에서 이어서 진행
```

### 사용 예시

```bash
# 특정 스킬만 처리
python skills/generate_skill_dataset.py --skills weather.md spotify.md

# 스킬 당 10 개 샘플 생성
python skills/generate_skill_dataset.py --num_samples 10

# 한 번의 요청에 스킬 10 개 묶기 (RPM 더 절약)
python skills/generate_skill_dataset.py --batch_size 10

# 무료 티어 RPM 한도가 가장 넉넉한 1.5 Flash 사용
python skills/generate_skill_dataset.py --model gemini-1.5-flash

# 배치 응답이 너무 커서 잘리면 batch_size 를 줄인다
python skills/generate_skill_dataset.py --batch_size 2

# 한 번에 한 스킬씩 (기존과 동일한 동작)
python skills/generate_skill_dataset.py --batch_size 1

# API 키 직접 전달
python skills/generate_skill_dataset.py --api_key AIza...

# 이어서 진행 (중간에 중단된 경우)
python skills/generate_skill_dataset.py --resume
```

## 배치 동작 방식

스킬 파일 목록은 `batch_size` 단위로 청크로 나뉘고, 각 청크는 **하나의 Gemini 요청**으로 전송된다.

- 스킬 25 개, `--batch_size 5` → Gemini 요청 5 번
- 스킬 25 개, `--batch_size 10` → Gemini 요청 3 번
- 스킬 25 개, `--batch_size 1` → Gemini 요청 25 번 (배치 비활성)

각 배치가 끝날 때마다 출력 파일이 갱신되므로 중간에 중단해도 그때까지의 결과는 보존된다.

`maxOutputTokens` 는 배치 크기 × `num_samples` 에 비례하여 자동으로 계산되며, Gemini 2.0 Flash 의 상한인 8192 토큰을 넘지 않는다. 응답이 잘리는 것 같으면 `--batch_size` 를 낮추거나 `--num_samples` 를 줄여라.

## 출력 데이터 형식

생성된 데이터셋은 다음과 같은 JSON 형식을 가집니다:

```json
[
  {
    "instruction": "Using weather functions, get correct result with given query",
    "query": "What's the weather like in Seoul today?",
    "tasks": ["weatherTask"],
    "responses": [
      "{'function_name': 'current', 'arguments': {'location': 'Seoul'}}"
    ]
  },
  {
    "instruction": "Using spotify functions, get correct result with given query",
    "query": "Play my favorite playlist",
    "tasks": ["spotifyTask"],
    "responses": [
      "{'function_name': 'play', 'arguments': {'context_uri': 'spotify:playlist:xxx'}}"
    ]
  }
]
```

## 메인 트레이닝 파이프라인과 연동

생성된 데이터셋은 `atomic/main_custom_weather.py` 의 `load_custom_weather_data` 함수와 호환됩니다.

```python
# main_custom_weather.py 에서 사용 예시
from main_custom_weather import load_custom_weather_data

data = load_custom_weather_data("skills/generated_datasets/train_data.json")
```

## 스킬 마크다운 파일 구조

각 스킬 마크다운 파일은 다음 형식을 따라야 합니다:

```markdown
---
id: com.argo.weather
name: Weather
version: "1.0.0"
description: Get current weather and forecasts via wttr.in
author: argo
tool_refs: [http_fetch]
tools: []
triggers: [weather, temperature, forecast, rain, snow]
---

# Weather Skill

...

## Verbs

### current
Get current conditions for a location.
...

### forecast
Get a 3-day forecast...
...
```

## LLM 프롬프트 / 응답 구조

스크립트는 **배치 안의 스킬 N 개를 한 프롬프트에 묶어** Gemini 에게 전송한다. 각 스킬에 대한 ID, 이름, 설명, 트리거, 함수 목록, 전체 마크다운 문서가 포함된다.

Gemini 는 다음 형식의 **JSON 오브젝트** 를 반환해야 한다 — key 는 스킬 ID, value 는 해당 스킬 샘플들의 배열.

```json
{
  "com.argo.weather": [
    {
      "query": "유저의 요청",
      "function_name": "함수명",
      "arguments": {"인자": "값"}
    }
  ],
  "com.argo.spotify": [
    {
      "query": "...",
      "function_name": "...",
      "arguments": {}
    }
  ]
}
```

응답이 ```` ```json ... ``` ```` 코드 펜스로 감싸져 와도 파서가 자동으로 벗긴다.

## 에러 처리

- API 키가 없는 경우: 에러 메시지 출력 후 종료
- Gemini API 호출 실패: 해당 배치 전체를 실패로 기록하고 다음 배치 진행
- JSON 파싱 실패: 원본 응답을 `batch_<skill_names>_raw_response.txt` 로 저장하여 디버깅 지원
- 배치 응답에 일부 스킬이 누락된 경우: 누락된 스킬만 실패로 기록되고 나머지는 정상 저장

## 확장 가능성

### 다른 LLM 프로바이더 지원

`call_llm_api` 함수와 `parse_llm_response_batch` 의 응답 추출 부분을 수정하면 OpenAI, Anthropic 등 다른 프로바이더로 바꿀 수 있다. 프롬프트 구조 (`generate_llm_prompt_batch`) 와 출력 데이터 포맷 (`format_for_natural_instructions`) 은 프로바이더와 독립적이라 그대로 재사용 가능하다.
