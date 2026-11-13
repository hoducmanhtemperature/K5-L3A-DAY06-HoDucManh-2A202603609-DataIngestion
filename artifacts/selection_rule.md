# Selection rule for the final holdout

The first test set and a second replacement test set were used in preliminary runs, reviewed, and set aside. Their questions, traces, and metrics are archived under `starter/benchmark/exploratory_superseded/`, `starter/results/exploratory_superseded/`, `starter/benchmark/exploratory_second/`, and `starter/results/exploratory_second/`. Neither is reported as the final holdout. The current test set is a third set fixed before its final run; prior test review still weakens the overall independence of this evaluation.

I fixed the following rule using the dev results only, before running the replacement test questions:

1. Choose the strategy with the highest dev Evidence Hit@3.
2. Break a tie with dev Hit@1.
3. If still tied, choose the simpler strategy without conditional filtering.

On the final recorded run, B has the highest dev Evidence Hit@3 (11/15), ahead of C (10/15) and A (7/15), so B is selected. A previous recorded run gave C 11/15; after rebuilding the Chroma HNSW index, C scored 10/15 on dev. The benchmark questions and strategy settings were unchanged. The cause of this run-to-run variation was not isolated; approximate-search variation is one possibility. It is recorded as a limitation of the one-run measurement. The third five-question test set in `starter/benchmark/questions.jsonl` is used for the final reported run. No chunk settings or model choices were changed after fixing that set.
