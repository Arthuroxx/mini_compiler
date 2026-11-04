// Valid program: exercises every compiler phase.
int a = 2;
int b = 3;
float ratio = 1;
int x = a + b * 5;
float y = x + ratio;

if (x >= 10) {
    x = x - 1;
} else {
    x = 0;
}

while (x >= 0) {
    x = x - 1;
}
