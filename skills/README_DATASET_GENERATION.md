# Skill Dataset Generator

## Overview

이 스크립트는 `skills/MDs/` 디렉토리에 있는 스킬 마크다운 파일들을 읽어들이고, LLM 을 사용하여 가상의 유저 쿼리와 해당 함수 호출 데이터를 자동으로 생성합니다. 생성된 데이터셋은 `NaturalInstructionsTaskDataset` 과 호환되는 형식으로 저장됩니다.

## 사용법

### 기본 사용법

```bash
# OPENAI_API_KEY 환경 변수 설정
export OPENAI_API_KEY="your-api-key-here"

# 모든 스킬 파일에 대해 데이터셋 생성 (스킬 당 5 개 샘플)
python skills/generate_skill_dataset.py
```

### 옵션

```
usage: generate_skill_dataset.py [-h] [--skills_dir SKILLS_DIR] 
                                 [--output_dir OUTPUT_DIR] 
                                 [--output_file OUTPUT_FILE] 
                                 [--num_samples NUM_SAMPLES] 
                                 [--api_key API_KEY] 
                                 [--model MODEL] 
                                 [--skills [SKILLS ...]] 
                                 [--resume]

options:
  --skills_dir          스킬 마크다운 파일이 있는 디렉토리 (기본값: skills/MDs)
  --output_dir          생성된 데이터셋을 저장할 디렉토리 (기본값: skills/generated_datasets)
  --output_file         출력 파일명 (기본값: train_data.json)
  --num_samples         스킬 당 생성할 샘플 수 (기본값: 5)
  --api_key             OpenAI API 키 (환경 변수 OPENAI_API_KEY 도 사용 가능)
  --model               사용할 LLM 모델 (기본값: gpt-4o-mini)
  --skills              처리할 특정 스킬 파일들 (기본값: 모든 .md 파일)
  --resume              기존 데이터셋에서 이어서 진행
```

### 사용 예시

```bash
# 특정 스킬만 처리
python skills/generate_skill_dataset.py --skills weather.md spotify.md

# 스킬 당 10 개 샘플 생성
python skills/generate_skill_dataset.py --num_samples 10

# 다른 모델 사용
python skills/generate_skill_dataset.py --model gpt-4o

# API 키 직접 전달
python skills/generate_skill_dataset.py --api_key sk-xxx

# 이어서 진행 (중간에 중단된 경우)
python skills/generate_skill_dataset.py --resume
```

## 출력 데이터 형식

생성된 데이터셋은 다음과 같은 JSON 형식을 가집니다:

```json
[
  {
    "instruction": "Using weather functions, get correct result with given query",
    "query": "What's the weather like in Seoul today?",
    "tasks": ["weatherTask"],
    "responses": [
      "{\"function_name\": \"current\", \"arguments\": {\"location\": \"Seoul\"}}"
    ]
  },
  {
    "instruction": "Using spotify functions, get correct result with given query",
    "query": "Play my favorite playlist",
    "tasks": ["spotifyTask"],
    "responses": [
      "{\"function_name\": \"play\", \"arguments\": {\"context_uri\": \"spotify:playlist:xxx\"}}"
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

## LLM 프롬프트 구조

스크립트는 각 스킬에 대해 다음과 같은 프롬프트를 생성하여 LLM 에게 전송합니다:

1. **Skill Information**: 스킬 ID, 이름, 설명, 트리거 키워드, 사용 가능한 함수 목록
2. **Full Skill Documentation**: 전체 마크다운 문서
3. **Task**: `num_samples` 개수의 가상의 유저 쿼리와 함수 호출 생성 요청

LLM 은 다음 형식의 JSON 배열을 반환해야 합니다:

```json
[
  {
    "query": "유저의 요청",
    "function_name": "함수명",
    "arguments": {"인자": "값"}
  }
]
```

## 에러 처리

- API 키가 없는 경우: 에러 메시지 출력 후 종료
- LLM API 호출 실패: 해당 스킬을 건너뛰고 다음 스킬 진행
- JSON 파싱 실패: 원본 응답을 `_raw_response.txt` 파일로 저장하여 디버깅 지원

## 확장 가능성

### 다른 LLM 프로바이더 지원

`call_llm_api` 함수를 수정하여 다른 LLM 프로바이더 (Anthropic, Google Gemini 등) 를 지원할 수 있습니다.

```python
def call_llm_api(prompt: str, api_key: str, model: str = "gpt-4o-mini") -> str:
    # OpenAI API 호출 코드
    # 또는 다른 프로바이더 API 호출 코드 추가 가능