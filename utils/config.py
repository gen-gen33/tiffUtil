import multiprocessing

NUM_WORKERS = min(8, multiprocessing.cpu_count() - 1)
print(f"cpu count: {multiprocessing.cpu_count()}")
print(f"number of workers: {NUM_WORKERS}")
