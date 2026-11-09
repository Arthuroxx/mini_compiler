// Four temporaries stay live at once, forcing a spill to the stack.
int a = 1;
int b = 2;
int c = 3;
int d = 4;
int e = 5;
int f = 6;
int g = 7;
int h = 8;
int x = (a + b) + ((c + d) + ((e + f) + (g + h)));
