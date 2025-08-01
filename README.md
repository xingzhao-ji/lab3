# You Spin Me Round Robin

A small C program that schedules tasks with round-robin. After every turn it picks a new time slice equal to the median of the CPU time still needed by the jobs in the queue.


## Building
Run this command in the same directory where the make file is located to build:
```shell
make
```

## Running

1. Create a workload file (example processes.txt):
```shell
cat processes.txt
4
1, 0, 7
2, 2, 4
3, 4, 1
4, 5, 4
```
2. Run the scheduler with the file name and an initial quantum (example 4):
```shell
./rr processes.txt 4
```
3. results:
```shell
Average waiting time: 4.50
Average response time: 3.25
```

## Cleaning up
To clean up the binary created, use this command
```shell
make clean
```
