# datasetLikeE2e —— 顶层命令入口（语法糖，实际调 run.py）
.PHONY: all run case help

all: run

run:
	python run.py --all

case:
	python run.py --case $(CASE)

help:
	@echo "make run             跑 cases/ 下全部样例（= make all）"
	@echo "make case CASE=<id>  跑单个样例，例如 make case CASE=CVE-2025-24928"
