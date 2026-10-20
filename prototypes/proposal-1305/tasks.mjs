export const STORAGE_KEY = "console-todo-1275.tasks.v1";
export const MAX_TASKS = 500;
export const MAX_TEXT = 240;

function validate(tasks) {
  if (!Array.isArray(tasks) || tasks.length > MAX_TASKS) throw new Error("Invalid saved task list.");
  const ids = new Set();
  return tasks.map(task => {
    if (!task || typeof task.id !== "string" || !/^[a-zA-Z0-9-]{1,100}$/.test(task.id) ||
        ids.has(task.id) || typeof task.text !== "string" || !task.text.trim() ||
        task.text.length > MAX_TEXT || typeof task.completed !== "boolean") {
      throw new Error("Invalid saved task list.");
    }
    ids.add(task.id);
    return { id: task.id, text: task.text, completed: task.completed };
  });
}

export function decodeTasks(value) {
  if (value === null) return [];
  if (typeof value !== "string" || value.length > 512_000) throw new Error("Invalid saved task list.");
  const data = JSON.parse(value);
  if (!data || data.version !== 1) throw new Error("Unsupported saved task list.");
  return validate(data.tasks);
}

export function encodeTasks(tasks) {
  return JSON.stringify({ version: 1, tasks: validate(tasks) });
}

export function addTask(tasks, text, id) {
  const trimmed = typeof text === "string" ? text.trim() : "";
  if (!trimmed || trimmed.length > MAX_TEXT) throw new Error("Write a task between 1 and 240 characters.");
  if (tasks.length >= MAX_TASKS) throw new Error("This list is full. Remove a task before adding another.");
  return validate([...tasks, { id, text: trimmed, completed: false }]);
}

export function toggleTask(tasks, id) {
  if (!tasks.some(task => task.id === id)) throw new Error("That task is no longer in this list.");
  return validate(tasks.map(task => task.id === id ? { ...task, completed: !task.completed } : task));
}

export function deleteTask(tasks, id) {
  if (!tasks.some(task => task.id === id)) throw new Error("That task is no longer in this list.");
  return validate(tasks.filter(task => task.id !== id));
}
