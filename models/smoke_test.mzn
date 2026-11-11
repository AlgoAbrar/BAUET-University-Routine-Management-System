% Minimal integration test: Python launches MiniZinc CLI and Gecode solves this.
var 1..9: x;
var 1..9: y;
constraint x + y = 10;
solve satisfy;
output ["MINIZINC_Working: x=", show(x), ", y=", show(y), "\n"];
