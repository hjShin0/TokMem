python TokMem/PrefDisco/evaluate.py \
  --checkpoint TokMem/atomic/saved_models/task_tokens_20260601_000158_best.pt \
  --model_name meta-llama/Llama-3.2-3B \
  --skill_md TokMem/skills/MDs/weather.md \
  --task_name WeatherTask \
  --queries queries.txt \
  --output weather_eval.json \
  --measured_device cuda:0 --oracle_device cuda:0 --baseline_device cuda:0
