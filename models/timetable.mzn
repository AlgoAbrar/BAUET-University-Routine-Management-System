int: N_BATCHES;
int: N_OFFERS;
int: N_TEACHERS;
int: N_ROOMS;
int: N_PERIODS;
int: N_DAYS;
int: MAX_SESSIONS;
int: N_PARALLEL_PAIRS;

set of int: BATCHES = 1..N_BATCHES;
set of int: OFFERS = 1..N_OFFERS;
set of int: TEACHERS = 1..N_TEACHERS;
set of int: ROOMS = 1..N_ROOMS;
set of int: PERIODS = 1..N_PERIODS;
set of int: DAYS = 1..N_DAYS;
set of int: PARALLEL_PAIRS = 1..N_PARALLEL_PAIRS;

int: THEORY = 1;
int: LAB = 2;
int: SUNDAY = 1;
int: THURSDAY = 5;

array[BATCHES] of int: BATCH_SIZE;
array[OFFERS] of int: OFFER_BATCH;
array[OFFERS] of int: OFFER_TYPE;                  % THEORY=1, LAB=2
array[OFFERS] of bool: OFFER_SHARED;
array[OFFERS] of int: OFFER_SESSIONS;
array[OFFERS] of bool: OFFER_DISTINCT_DAYS;
set of int: EVENTS = 1..sum(o in OFFERS)(OFFER_SESSIONS[o]);
array[OFFERS] of int: OFFER_DURATION;              % consecutive periods per session
array[OFFERS] of int: OFFER_TEACHER_COUNT;         % 1 or 2
array[OFFERS] of int: OFFER_LOAD_HALF_UNITS;       % workload per assigned teacher, x2
array[OFFERS] of int: OFFER_CONTACT_HALF_UNITS;    % total course contact hours, x2
array[OFFERS] of int: FIXED_TEACHER_1;             % 0 for solver-assigned theory
array[OFFERS] of int: FIXED_TEACHER_2;             % 0 for solver-assigned theory
array[EVENTS] of int: EVENT_OFFER;
array[PARALLEL_PAIRS] of int: PAIR_OFFER_1;
array[PARALLEL_PAIRS] of int: PAIR_OFFER_2;
array[PARALLEL_PAIRS] of int: PAIR_SESSIONS;

array[TEACHERS] of int: TEACHER_BASE_HALF_UNITS;
array[TEACHERS] of int: TEACHER_HARD_HALF_UNITS;
array[TEACHERS] of int: TEACHER_EXTRA_HALF_UNITS;
array[TEACHERS] of bool: TEACHER_IS_EXTERNAL;
array[TEACHERS, DAYS] of bool: TEACHER_AVAILABLE;

array[ROOMS] of int: ROOM_ID;
array[ROOMS] of int: ROOM_CAPACITY;
array[ROOMS] of bool: ROOM_FOR_THEORY;
array[ROOMS] of bool: ROOM_FOR_LAB;
int: LARGE_THEORY_ROOM;                            % room 202's index

array[1..N_OFFERS, 1..MAX_SESSIONS] of int: OFFER_EVENT_BY_SESSION;

% The event index list is created in the same order as the Python flattening.
array[EVENTS] of int: EVENT_BATCH = [OFFER_BATCH[EVENT_OFFER[e]] | e in EVENTS];
array[EVENTS] of int: EVENT_TYPE = [OFFER_TYPE[EVENT_OFFER[e]] | e in EVENTS];
array[EVENTS] of int: EVENT_DURATION = [OFFER_DURATION[EVENT_OFFER[e]] | e in EVENTS];

array[OFFERS] of var 1..N_TEACHERS: OFFER_TEACHER_1;
array[OFFERS] of var 0..N_TEACHERS: OFFER_TEACHER_2; % 0 means no second instructor
array[EVENTS] of var DAYS: EVENT_DAY;
array[EVENTS] of var 1..N_PERIODS: EVENT_START;
array[EVENTS] of var ROOMS: EVENT_ROOM;
array[EVENTS] of var 0..N_ROOMS: EVENT_ROOM_2; % optional second lab room; 0 means unused
array[EVENTS] of var 1..70: EVENT_REQUIRED_ROOM_CAPACITY;

int: MAX_POSSIBLE_LOAD = sum(o in OFFERS)(2 * OFFER_LOAD_HALF_UNITS[o]);
array[TEACHERS] of var 0..MAX_POSSIBLE_LOAD: TEACHER_LOAD_HALF_UNITS;
array[TEACHERS] of var 0..max(TEACHER_EXTRA_HALF_UNITS): TEACHER_OVERLOAD_HALF_UNITS;

% Soft preference: minimize same-day pairs of theory meetings for one offering.
var int: THEORY_SAME_DAY_PAIR_PENALTY =
  sum(o in OFFERS where OFFER_TYPE[o] = THEORY)(
    sum(s1, s2 in 1..OFFER_SESSIONS[o] where s1 < s2)(
      bool2int(
        EVENT_DAY[OFFER_EVENT_BY_SESSION[o,s1]] =
        EVENT_DAY[OFFER_EVENT_BY_SESSION[o,s2]]
      )
    )
  );

% Exactly one or two instructors per offering. Shared theory uses exactly two.
constraint forall(o in OFFERS)(
  OFFER_TEACHER_1[o] >= 1 /\ OFFER_TEACHER_1[o] <= N_TEACHERS
);
constraint forall(o in OFFERS)(
  if OFFER_TYPE[o] = LAB then
    OFFER_TEACHER_1[o] = FIXED_TEACHER_1[o] /\
    OFFER_TEACHER_2[o] = FIXED_TEACHER_2[o] /\
    OFFER_TEACHER_1[o] != OFFER_TEACHER_2[o]
  elseif OFFER_TEACHER_COUNT[o] = 1 then
    OFFER_TEACHER_2[o] = 0
  else
    OFFER_TEACHER_2[o] >= 1 /\
    OFFER_TEACHER_2[o] <= N_TEACHERS /\
    OFFER_TEACHER_1[o] < OFFER_TEACHER_2[o]
  endif
);
constraint forall(o in OFFERS)(
  if OFFER_TYPE[o] = LAB then
    OFFER_TEACHER_COUNT[o] = 2
  elseif OFFER_SHARED[o] then
    OFFER_TEACHER_COUNT[o] = 2
  else
    OFFER_TEACHER_COUNT[o] = 1
  endif
);

% Fixed lab teachers may not be external teachers (external staff are theory-only).
constraint forall(o in OFFERS where OFFER_TYPE[o] = LAB)(
  not TEACHER_IS_EXTERNAL[FIXED_TEACHER_1[o]] /\
  not TEACHER_IS_EXTERNAL[FIXED_TEACHER_2[o]]
);

% Schedule every event within the teaching day and do not cross the two breaks.
constraint forall(e in EVENTS)(
  EVENT_START[e] + EVENT_DURATION[e] - 1 <= N_PERIODS
);
constraint forall(e in EVENTS)(
  if EVENT_DURATION[e] = 1 then true
  elseif EVENT_DURATION[e] = 2 then
    EVENT_START[e] = 1 \/ EVENT_START[e] = 2 \/
    EVENT_START[e] = 4 \/ EVENT_START[e] = 5
  elseif EVENT_DURATION[e] = 3 then
    EVENT_START[e] = 1 \/ EVENT_START[e] = 4
  else
    false
  endif
);

% A twice-weekly lab meets on two different days, not twice on one day.
constraint forall(o in OFFERS where OFFER_DISTINCT_DAYS[o])(
  forall(s1,s2 in 1..OFFER_SESSIONS[o] where s1 < s2)(
    EVENT_DAY[OFFER_EVENT_BY_SESSION[o,s1]] != EVENT_DAY[OFFER_EVENT_BY_SESSION[o,s2]]
  )
);

% Hard theory rule: one course offering may occupy at most two periods per day.
% Labs are exempt because their required consecutive blocks can be three periods.
constraint forall(o in OFFERS where OFFER_TYPE[o] = THEORY, d in DAYS)(
  sum(s in 1..OFFER_SESSIONS[o])(
    bool2int(EVENT_DAY[OFFER_EVENT_BY_SESSION[o,s]] = d) * OFFER_DURATION[o]
  ) <= 2
);

% Symmetry breaking for otherwise interchangeable repeated meetings.
constraint forall(o in OFFERS, s in 1..(OFFER_SESSIONS[o]-1))(
  let {
    int: e1 = OFFER_EVENT_BY_SESSION[o,s],
    int: e2 = OFFER_EVENT_BY_SESSION[o,s+1]
  } in
    EVENT_DAY[e1] < EVENT_DAY[e2] \/
    (EVENT_DAY[e1] = EVENT_DAY[e2] /\ EVENT_START[e1] <= EVENT_START[e2])
);

% Every fixed pair in parallel_lab_pairs.csv must meet simultaneously for each weekly session.
constraint forall(p in PARALLEL_PAIRS, s in 1..PAIR_SESSIONS[p])(
  let {
    int: e1 = OFFER_EVENT_BY_SESSION[PAIR_OFFER_1[p],s],
    int: e2 = OFFER_EVENT_BY_SESSION[PAIR_OFFER_2[p],s]
  } in
    EVENT_DAY[e1] = EVENT_DAY[e2] /\
    EVENT_START[e1] = EVENT_START[e2] /\
    EVENT_DURATION[e1] = EVENT_DURATION[e2] /\
    EVENT_ROOM[e1] != EVENT_ROOM[e2]
);

% No overlapping events for the same batch, except two different lab offerings
% scheduled in exactly the same block. That represents the implicit student split.
constraint forall(i,j in EVENTS where i < j)(
  if EVENT_BATCH[i] = EVENT_BATCH[j] /\
     EVENT_DAY[i] = EVENT_DAY[j] /\
     EVENT_START[i] <= EVENT_START[j] + EVENT_DURATION[j] - 1 /\
     EVENT_START[j] <= EVENT_START[i] + EVENT_DURATION[i] - 1
  then
    EVENT_TYPE[i] = LAB /\ EVENT_TYPE[j] = LAB /\
    EVENT_OFFER[i] != EVENT_OFFER[j] /\
    EVENT_START[i] = EVENT_START[j] /\
    EVENT_DURATION[i] = EVENT_DURATION[j]
  else true endif
);

% A lab can have at most one simultaneous lab partner: no third concurrent lab.
constraint forall(i in EVENTS)(
  sum(j in EVENTS where j != i)(
    bool2int(
      EVENT_BATCH[i] = EVENT_BATCH[j] /\
      EVENT_TYPE[i] = LAB /\ EVENT_TYPE[j] = LAB /\
      EVENT_OFFER[i] != EVENT_OFFER[j] /\
      EVENT_DAY[i] = EVENT_DAY[j] /\
      EVENT_START[i] = EVENT_START[j] /\
      EVENT_DURATION[i] = EVENT_DURATION[j]
    )
  ) <= 1
);

% No teacher can be committed to two overlapping events. Shared-theory teachers
% are conservatively considered occupied for all of the course's timetable periods.
constraint forall(i,j in EVENTS where i < j)(
  if EVENT_DAY[i] = EVENT_DAY[j] /\
     EVENT_START[i] <= EVENT_START[j] + EVENT_DURATION[j] - 1 /\
     EVENT_START[j] <= EVENT_START[i] + EVENT_DURATION[i] - 1
  then
    not (
      OFFER_TEACHER_1[EVENT_OFFER[i]] = OFFER_TEACHER_1[EVENT_OFFER[j]] \/
      (OFFER_TEACHER_2[EVENT_OFFER[i]] > 0 /\ OFFER_TEACHER_2[EVENT_OFFER[i]] = OFFER_TEACHER_1[EVENT_OFFER[j]]) \/
      (OFFER_TEACHER_2[EVENT_OFFER[j]] > 0 /\ OFFER_TEACHER_1[EVENT_OFFER[i]] = OFFER_TEACHER_2[EVENT_OFFER[j]]) \/
      (OFFER_TEACHER_2[EVENT_OFFER[i]] > 0 /\ OFFER_TEACHER_2[EVENT_OFFER[j]] > 0 /\
       OFFER_TEACHER_2[EVENT_OFFER[i]] = OFFER_TEACHER_2[EVENT_OFFER[j]])
    )
  else true endif
);

% Enforce teacher availability for every period occupied by an event.
constraint forall(e in EVENTS, t in TEACHERS, d in DAYS)(
  (EVENT_DAY[e] = d /\
   (OFFER_TEACHER_1[EVENT_OFFER[e]] = t \/ OFFER_TEACHER_2[EVENT_OFFER[e]] = t))
  -> TEACHER_AVAILABLE[t,d]
);

% Calculate the number of students a lab event must serve in its room(s).
% When two courses run in parallel, each serves an implicit half-batch; otherwise
% a single-course lab serves the whole batch and may be split across two rooms.
constraint forall(e in EVENTS)(
  EVENT_REQUIRED_ROOM_CAPACITY[e] =
    if EVENT_TYPE[e] = LAB /\ sum(j in EVENTS where j != e)(
      bool2int(EVENT_BATCH[e] = EVENT_BATCH[j] /\ EVENT_TYPE[j] = LAB /\
               EVENT_OFFER[e] != EVENT_OFFER[j] /\ EVENT_DAY[e] = EVENT_DAY[j] /\
               EVENT_START[e] = EVENT_START[j] /\ EVENT_DURATION[e] = EVENT_DURATION[j])
    ) > 0 then
      (BATCH_SIZE[EVENT_BATCH[e]] + 1) div 2
    else
      BATCH_SIZE[EVENT_BATCH[e]]
    endif
);

% Room 1 is always assigned. The second room is optional and lab-only.
constraint forall(e in EVENTS, r in ROOMS)(
  if EVENT_ROOM[e] = r then
    if EVENT_TYPE[e] = THEORY then
      ROOM_FOR_THEORY[r] /\
      ROOM_CAPACITY[r] >= BATCH_SIZE[EVENT_BATCH[e]] /\
      EVENT_ROOM_2[e] = 0 /\
      (BATCH_SIZE[EVENT_BATCH[e]] <= 60 \/ r = LARGE_THEORY_ROOM)
    else
      ROOM_FOR_LAB[r]
    endif
  else true endif
);
constraint forall(e in EVENTS, r in ROOMS)(
  if EVENT_ROOM_2[e] = r then EVENT_TYPE[e] = LAB /\ ROOM_FOR_LAB[r] else true endif
);
constraint forall(e in EVENTS, r1,r2 in ROOMS)(
  if EVENT_ROOM[e] = r1 /\ EVENT_ROOM_2[e] = r2 /\ r2 > 0 then
    r1 != r2 /\ ROOM_CAPACITY[r1] + ROOM_CAPACITY[r2] >= EVENT_REQUIRED_ROOM_CAPACITY[e]
  else true endif
);
constraint forall(e in EVENTS, r in ROOMS)(
  if EVENT_ROOM[e] = r /\ EVENT_TYPE[e] = LAB /\ EVENT_ROOM_2[e] = 0 then
    ROOM_CAPACITY[r] >= EVENT_REQUIRED_ROOM_CAPACITY[e]
  else true endif
);

% Every room used by an event must be free for all its occupied periods.
constraint forall(i,j in EVENTS where i < j)(
  if EVENT_DAY[i] = EVENT_DAY[j] /\
     EVENT_START[i] <= EVENT_START[j] + EVENT_DURATION[j] - 1 /\
     EVENT_START[j] <= EVENT_START[i] + EVENT_DURATION[i] - 1
  then
    EVENT_ROOM[i] != EVENT_ROOM[j] /\
    (EVENT_ROOM_2[j] = 0 \/ EVENT_ROOM[i] != EVENT_ROOM_2[j]) /\
    (EVENT_ROOM_2[i] = 0 \/ EVENT_ROOM_2[i] != EVENT_ROOM[j]) /\
    (EVENT_ROOM_2[i] = 0 \/ EVENT_ROOM_2[j] = 0 \/ EVENT_ROOM_2[i] != EVENT_ROOM_2[j])
  else true endif
);

% Weekly workload accounting in half-hour units.
% Shared theory is divided evenly; labs are charged to both fixed co-teachers.
constraint forall(t in TEACHERS)(
  TEACHER_LOAD_HALF_UNITS[t] = sum(o in OFFERS)(
    (if OFFER_TEACHER_1[o] = t then OFFER_LOAD_HALF_UNITS[o] else 0 endif) +
    (if OFFER_TEACHER_2[o] = t then OFFER_LOAD_HALF_UNITS[o] else 0 endif)
  )
);
constraint forall(t in TEACHERS)(
  TEACHER_LOAD_HALF_UNITS[t] <= TEACHER_HARD_HALF_UNITS[t] /\
  TEACHER_OVERLOAD_HALF_UNITS[t] >= TEACHER_LOAD_HALF_UNITS[t] - TEACHER_BASE_HALF_UNITS[t] /\
  TEACHER_OVERLOAD_HALF_UNITS[t] <= TEACHER_EXTRA_HALF_UNITS[t]
);

% Each external teacher has exactly one course: one non-shared 3-hour theory
% offering, scheduled Thursday as three consecutive periods, and no other course.
constraint forall(t in TEACHERS where TEACHER_IS_EXTERNAL[t])(
  sum(o in OFFERS)(bool2int(OFFER_TEACHER_1[o] = t \/ OFFER_TEACHER_2[o] = t)) = 1 /\
  sum(o in OFFERS)(bool2int(
    (OFFER_TEACHER_1[o] = t \/ OFFER_TEACHER_2[o] = t) /\
    OFFER_TYPE[o] = THEORY /\ not OFFER_SHARED[o] /\
    OFFER_CONTACT_HALF_UNITS[o] = 6 /\ OFFER_SESSIONS[o] = 3 /\
    OFFER_TEACHER_COUNT[o] = 1
  )) = 1 /\
  TEACHER_LOAD_HALF_UNITS[t] = 6
);
constraint forall(t in TEACHERS where TEACHER_IS_EXTERNAL[t], o in OFFERS)(
  if OFFER_TEACHER_1[o] = t \/ OFFER_TEACHER_2[o] = t then
    OFFER_TYPE[o] = THEORY /\ not OFFER_SHARED[o] /\
    OFFER_CONTACT_HALF_UNITS[o] = 6 /\ OFFER_SESSIONS[o] = 3 /\
    EVENT_DAY[OFFER_EVENT_BY_SESSION[o,1]] = THURSDAY /\
    (EVENT_START[OFFER_EVENT_BY_SESSION[o,1]] = 1 \/
     EVENT_START[OFFER_EVENT_BY_SESSION[o,1]] = 4) /\
    forall(s in 1..(OFFER_SESSIONS[o]-1))(
      EVENT_DAY[OFFER_EVENT_BY_SESSION[o,s+1]] = THURSDAY /\
      EVENT_START[OFFER_EVENT_BY_SESSION[o,s+1]] = EVENT_START[OFFER_EVENT_BY_SESSION[o,s]] + 1
    )
  else true endif
);

% Assign theory teachers, then interleave each event's day and start time, and
% finally choose rooms. Minimize same-day repeats among theory meetings as a soft preference.
array[1..2 * card(EVENTS)] of var int: EVENT_TIME_SEARCH =
  [if i mod 2 = 1 then EVENT_DAY[(i + 1) div 2] else EVENT_START[(i + 1) div 2] endif
   | i in 1..2 * card(EVENTS)];

solve :: seq_search([
  int_search(EVENT_TIME_SEARCH, first_fail, indomain_random, complete),
  int_search([OFFER_TEACHER_1[o] | o in OFFERS where OFFER_TYPE[o] = THEORY], first_fail, indomain_min, complete),
  int_search([OFFER_TEACHER_2[o] | o in OFFERS where OFFER_TYPE[o] = THEORY /\ OFFER_TEACHER_COUNT[o] = 2], first_fail, indomain_min, complete),
  int_search([EVENT_ROOM[e] | e in EVENTS], first_fail, indomain_min, complete),
  int_search([EVENT_ROOM_2[e] | e in EVENTS], first_fail, indomain_min, complete)
]) minimize THEORY_SAME_DAY_PAIR_PENALTY;

output ["STATUS=OPTIMAL_OR_FEASIBLE\n",
        "THEORY_SPREAD_PENALTY|" ++ show(THEORY_SAME_DAY_PAIR_PENALTY) ++ "\n"] ++
  ["EVENT|" ++ show(e) ++ "|" ++ show(EVENT_OFFER[e]) ++ "|" ++
   show(EVENT_DAY[e]) ++ "|" ++ show(EVENT_START[e]) ++ "|" ++
   show(EVENT_DURATION[e]) ++ "|" ++ show(OFFER_TEACHER_1[EVENT_OFFER[e]]) ++ "|" ++
   show(OFFER_TEACHER_2[EVENT_OFFER[e]]) ++ "|" ++ show(EVENT_ROOM[e]) ++ "|" ++
   show(EVENT_ROOM_2[e]) ++ "\n"
   | e in EVENTS] ++
  ["LOAD_HALF_UNITS|" ++ show(t) ++ "|" ++ show(TEACHER_LOAD_HALF_UNITS[t]) ++ "|" ++
   show(TEACHER_OVERLOAD_HALF_UNITS[t]) ++ "\n" | t in TEACHERS];
