import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

BASE = Path("docs/evaluation")
CSV = BASE / "PES1UG24AM207_configuration_comparison.csv"
OUT = BASE / "charts"
OUT.mkdir(exist_ok=True)

df = pd.read_csv(CSV)

# 1. Average retrieval latency by embedding model
model_latency = df.groupby("model")["latency_mean_ms"].mean().sort_values()
plt.figure(figsize=(8, 5))
model_latency.plot(kind="bar")
plt.title("Average Retrieval Latency by Embedding Model")
plt.xlabel("Embedding Model")
plt.ylabel("Mean Latency (ms)")
plt.xticks(rotation=0)
plt.tight_layout()
plt.savefig(OUT / "model_latency_comparison.png", dpi=200)
plt.close()

# 2. Average precision by chunking strategy
strategy_precision = df.groupby("strategy")["precision_at_3"].mean().sort_values(ascending=False)
plt.figure(figsize=(8, 5))
strategy_precision.plot(kind="bar")
plt.title("Average Precision@3 by Chunking Strategy")
plt.xlabel("Chunking Strategy")
plt.ylabel("Mean Precision@3")
plt.ylim(0, 1)
plt.xticks(rotation=0)
plt.tight_layout()
plt.savefig(OUT / "chunking_strategy_precision.png", dpi=200)
plt.close()

# 3. Average retrieval latency by chunk size
chunk_latency = df.groupby("chunk_words")["latency_mean_ms"].mean().sort_index()
plt.figure(figsize=(8, 5))
chunk_latency.plot(kind="bar")
plt.title("Average Retrieval Latency by Chunk Size")
plt.xlabel("Chunk Size (words)")
plt.ylabel("Mean Latency (ms)")
plt.xticks(rotation=0)
plt.tight_layout()
plt.savefig(OUT / "chunk_size_latency.png", dpi=200)
plt.close()

# 4. Retrieval latency across all 18 configurations
ranked = df.sort_values("rank")
labels = [
    f'{row["rank"]}. {row["model"]} / {row["strategy"]} / {row["chunk_words"]}'
    for _, row in ranked.iterrows()
]
plt.figure(figsize=(13, 7))
plt.barh(labels[::-1], ranked["latency_mean_ms"].iloc[::-1])
plt.title("Retrieval Latency Across 18 Configurations")
plt.xlabel("Mean Retrieval Latency (ms)")
plt.ylabel("Ranked Configuration")
plt.tight_layout()
plt.savefig(OUT / "all_configuration_latency.png", dpi=200)
plt.close()

print("Created charts:")
for path in sorted(OUT.glob("*.png")):
    print(path)
