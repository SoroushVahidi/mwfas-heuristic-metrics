/* Input/output driver for the unmodified Bader-Research productivity C library.
 * This runs its documented Okubo and serial Toposhuffle annealing components.
 * It is not the paper's complete JAX Rocket-Crane pipeline.
 */
#include <errno.h>
#include <limits.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

#include "connectome.h"
#include "solution_instance.h"
#include "okubo_ls.h"
#include "simanneal_finetune.h"

static long long parse_ll(const char *value) {
    char *end = NULL;
    errno = 0;
    long long result = strtoll(value, &end, 10);
    if (errno || end == value || *end != '\0') {
        fprintf(stderr, "invalid integer: %s\n", value);
        exit(2);
    }
    return result;
}

int main(int argc, char **argv) {
    if (argc != 8) {
        fprintf(stderr, "usage: driver input.csv output.txt seed okubo_epochs iterations go_back_window toposhuffle_frequency\n");
        return 2;
    }
    long long seed_value = parse_ll(argv[3]);
    long long epochs = parse_ll(argv[4]);
    long long iterations = parse_ll(argv[5]);
    long long window = parse_ll(argv[6]);
    long long frequency = parse_ll(argv[7]);
    if (seed_value < 0 || seed_value > UINT_MAX || epochs < 0 || epochs > INT_MAX ||
        iterations < 0 || window < 0 || window > INT_MAX || frequency < 0 || frequency > INT_MAX) {
        fprintf(stderr, "parameter outside supported range\n");
        return 2;
    }
    seed_rng((unsigned int)seed_value);
    Connectome *graph = load_connectome(argv[1]);
    if (!graph || graph->num_nodes <= 0 || graph->num_nodes > INT_MAX) return 3;

    /* The authors' example starts with a random permutation. Supplying one
     * through their public constructor makes the stated seed effective; their
     * create_random_solution_instance() mixes in wall-clock time. */
    int *initial = malloc((size_t)graph->num_nodes * sizeof(int));
    if (!initial) return 3;
    for (long i = 0; i < graph->num_nodes; ++i) initial[i] = (int)i;
    for (long i = graph->num_nodes - 1; i > 0; --i) {
        long j = (long)(random_u32() % (uint32_t)(i + 1));
        int tmp = initial[i]; initial[i] = initial[j]; initial[j] = tmp;
    }
    SolutionInstance *instance = create_solution_instance(graph, initial, true);
    free(initial);
    if (!instance) return 3;
    BestSolutionStorage *best = create_best_solution_storage();
    if (!best) return 3;
    init_best_solution_storage(best, instance);
    run_okubo_local_search(instance, graph, (int)epochs, false, 10000);
    update_best_solution_storage_if_better(best, instance);
    run_simanneal_with_toposhuffle(instance, graph, iterations, 0, 0.001, 0.1,
                                  (int)window, (int)frequency, 0, best);
    update_best_solution_storage_if_better(best, instance);

    if (!best->best_solution_array || best->solution_size != graph->num_nodes) return 4;
    FILE *out = fopen(argv[2], "w");
    if (!out) return 4;
    fprintf(out, "forward_score\t%lld\n", best->best_score);
    for (long i = 0; i < graph->num_nodes; ++i) {
        int dense = best->best_solution_array[i];
        if (dense < 0 || dense >= graph->num_nodes) return 4;
        fprintf(out, "%llu\n", (unsigned long long)graph->dense_idx_to_node_id[dense]);
    }
    if (fclose(out) != 0) return 4;
    free_best_solution_storage(best);
    free_solution_instance(instance);
    free_connectome(graph);
    return 0;
}
