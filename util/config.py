import multiprocessing

NUM_WORKERS = min(8, multiprocessing.cpu_count())
print(f"cpu coung: {NUM_WORKERS}")
