#include "stdio.h"
#include "stdint.h"
#include <unistd.h>

#include <chrono>
#include <ctime>    

uint8_t quit = 0;

void sigint_handler (int sig) {
    printf("sig abort %d\n", sig);
    quit = 1;
}


int main(int argc, char const *argv[])
{
    printf("Service Hello World\n");
    uint32_t cnt = 0;
    time_t rawtime;
  
    while (!quit)
    {
        time (&rawtime);
        sleep(2);
        printf("%s Hello %d\n", std::ctime(&rawtime), cnt);
        cnt++;
    }
    
    return 0;
}
