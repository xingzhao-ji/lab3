/* rr.c – complete round‑robin simulator ---------------------------------- */
/* CS 111 Lab 3 skeleton extended with a full implementation                */
/* Tested with:  gcc ‑std=c11 ‑Wall ‑Wextra rr.c ‑o rr                      */

#include <errno.h>
#include <fcntl.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/queue.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>

typedef uint32_t u32;
typedef int32_t  i32;

/* ----------------------------------------------------------------------- */
/* Process descriptor                                                      */
struct process {
    u32 pid;
    u32 arrival_time;
    u32 burst_time;

    TAILQ_ENTRY(process) pointers;       /* linkage for ready‑queue        */

    /* -------- additional scheduler state -------- */
    u32  remaining_time;   /* CPU time still required                    */
    bool responded;        /* has the process been scheduled before?     */
    bool arrived;          /* has it entered the ready‑queue yet?        */
};
/* ----------------------------------------------------------------------- */

TAILQ_HEAD(process_list, process);

/* ------------------------- helper: parse decimal ----------------------- */
u32 next_int(const char **data, const char *data_end)
{
    u32 current = 0;
    bool started = false;
    while (*data != data_end) {
        char c = **data;

        if (c < '0' || c > '9') {
            if (started) return current;          /* finished one number  */
        } else {
            if (!started) {
                current  = (c - '0');
                started  = true;
            } else {
                current *= 10;
                current += (c - '0');
            }
        }
        ++(*data);
    }
    fprintf(stderr, "Reached end of file while looking for another integer\n");
    exit(EINVAL);
}

u32 next_int_from_c_str(const char *data)
{
    char c;
    u32  i = 0, current = 0;
    bool started = false;

    while ((c = data[i++])) {
        if (c < '0' || c > '9') exit(EINVAL);
        if (!started) {
            current = (c - '0');
            started = true;
        } else {
            current *= 10;
            current += (c - '0');
        }
    }
    return current;
}

/* -------------------- load file into array of processes ---------------- */
void init_processes(const char *path,
                    struct process **process_data,
                    u32 *process_size)
{
    int fd = open(path, O_RDONLY);
    if (fd == -1) { perror("open"); exit(errno); }

    struct stat st;
    if (fstat(fd, &st) == -1) { perror("stat"); exit(errno); }

    u32 size = st.st_size;
    const char *data_start = mmap(NULL, size, PROT_READ, MAP_PRIVATE, fd, 0);
    if (data_start == MAP_FAILED) { perror("mmap"); exit(errno); }

    const char *data_end = data_start + size;
    const char *data     = data_start;

    *process_size = next_int(&data, data_end);

    *process_data = calloc(*process_size, sizeof(struct process));
    if (!*process_data) { perror("calloc"); exit(errno); }

    for (u32 i = 0; i < *process_size; ++i) {
        (*process_data)[i].pid          = next_int(&data, data_end);
        (*process_data)[i].arrival_time = next_int(&data, data_end);
        (*process_data)[i].burst_time   = next_int(&data, data_end);
    }

    munmap((void *)data_start, size);
    close(fd);
}

/* ======================================================================= */
int main(int argc, char *argv[])
{
    if (argc != 3) return EINVAL;

    struct process *data;
    u32 size;
    init_processes(argv[1], &data, &size);

    u32 quantum_length = next_int_from_c_str(argv[2]);
    if (quantum_length == 0) return EINVAL;

    struct process_list ready;
    TAILQ_INIT(&ready);

    u32 total_waiting_time  = 0;
    u32 total_response_time = 0;

    /* ----------------------- scheduler initialisation ------------------ */
    for (u32 i = 0; i < size; ++i) {
        data[i].remaining_time = data[i].burst_time;
        data[i].responded      = false;
        data[i].arrived        = false;
    }

    u32 completed = 0;    /* how many processes have finished              */
    u32 time      = 0;    /* global clock in units                         */

    /* ----------------------------- main loop --------------------------- */
    while (completed < size) {

        /* admit any newly‑arrived processes */
        for (u32 i = 0; i < size; ++i)
            if (!data[i].arrived && data[i].arrival_time <= time) {
                TAILQ_INSERT_TAIL(&ready, &data[i], pointers);
                data[i].arrived = true;
            }

        /* if CPU idle, jump to next arrival to avoid useless ticks */
        if (TAILQ_EMPTY(&ready)) {
            u32 next = UINT32_MAX;
            for (u32 i = 0; i < size; ++i)
                if (!data[i].arrived && data[i].arrival_time < next)
                    next = data[i].arrival_time;
            time = next;
            continue;
        }

        /* select the head of the queue */
        struct process *p = TAILQ_FIRST(&ready);
        TAILQ_REMOVE(&ready, p, pointers);

        /* first time on CPU ⇒ response time */
        if (!p->responded) {
            total_response_time += time - p->arrival_time;
            p->responded = true;
        }

        /* run for one quantum or until finished */
        u32 slice = (p->remaining_time < quantum_length)
                      ? p->remaining_time
                      : quantum_length;

        u32 start_time = time;
        time          += slice;
        p->remaining_time -= slice;

        /* admit jobs that arrived during this slice */
        for (u32 i = 0; i < size; ++i)
            if (!data[i].arrived &&
                data[i].arrival_time > start_time &&
                data[i].arrival_time <= time) {
                TAILQ_INSERT_TAIL(&ready, &data[i], pointers);
                data[i].arrived = true;
            }

        /* either re‑queue the still‑running job or finish it */
        if (p->remaining_time > 0) {
            TAILQ_INSERT_TAIL(&ready, p, pointers);
        } else {
            ++completed;
            total_waiting_time += time - p->arrival_time - p->burst_time;
        }
    }
    /* --------------------------- end scheduler ------------------------- */

    printf("Average waiting time: %.2f\n",
           (float)total_waiting_time  / (float)size);
    printf("Average response time: %.2f\n",
           (float)total_response_time / (float)size);

    free(data);
    return 0;
}
