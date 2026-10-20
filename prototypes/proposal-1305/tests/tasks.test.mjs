import test from "node:test";
import assert from "node:assert/strict";
import { addTask, toggleTask, deleteTask, encodeTasks, decodeTasks, MAX_TASKS } from "../tasks.mjs";

test("a new list is empty, without synthetic seed tasks", () => {
  assert.deepEqual(decodeTasks(null), []);
});
test("add trims input and leaves the previous list unchanged", () => {
  const before = [];
  const after = addTask(before, "  Read a book  ", "task-1");
  assert.deepEqual(after, [{ id: "task-1", text: "Read a book", completed: false }]);
  assert.deepEqual(before, []);
});
test("blank and oversized input are rejected", () => {
  assert.throws(() => addTask([], "  ", "task-1"));
  assert.throws(() => addTask([], "a".repeat(241), "task-1"));
});
test("completion can be toggled both ways without changing another task", () => {
  const tasks = addTask(addTask([], "First", "task-1"), "Second", "task-2");
  const done = toggleTask(tasks, "task-1");
  assert.equal(done[0].completed, true);
  assert.equal(done[1].completed, false);
  assert.deepEqual(toggleTask(done, "task-1"), tasks);
  assert.equal(tasks[0].completed, false);
});
test("delete affects only the selected task and unknown identities fail", () => {
  const tasks = addTask(addTask([], "First", "task-1"), "Second", "task-2");
  assert.deepEqual(deleteTask(tasks, "task-1"), [tasks[1]]);
  assert.throws(() => toggleTask(tasks, "unknown"));
  assert.throws(() => deleteTask(tasks, "unknown"));
});
test("saved data round-trips text and completion, including inert HTML-looking text", () => {
  const tasks = toggleTask(addTask([], '<img src=x onerror="alert(1)">', "task-1"), "task-1");
  assert.deepEqual(decodeTasks(encodeTasks(tasks)), tasks);
});
test("corrupt or future data is rejected, never silently converted into an empty saved list", () => {
  for (const value of ["broken-json", "null", "[]", '{"version":2,"tasks":[]}', '{"version":1,"tasks":{}}']) {
    assert.throws(() => decodeTasks(value));
  }
});
test("invalid types and duplicate identities are rejected", () => {
  const task = { id: "task-1", text: "First", completed: false };
  for (const tasks of [[task, task], [{ ...task, completed: "false" }], [{ ...task, text: " " }], [{ ...task, id: "bad id" }]]) {
    assert.throws(() => encodeTasks(tasks));
  }
});
test("list and serialized data bounds are explicit", () => {
  const tasks = Array.from({ length: MAX_TASKS }, (_, i) => ({ id: `task-${i}`, text: "Task", completed: false }));
  assert.equal(decodeTasks(encodeTasks(tasks)).length, MAX_TASKS);
  assert.throws(() => addTask(tasks, "One more", "task-extra"));
  assert.throws(() => decodeTasks(" ".repeat(512_001)));
});
