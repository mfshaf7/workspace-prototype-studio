import { STORAGE_KEY, addTask, toggleTask, deleteTask, decodeTasks, encodeTasks } from "./tasks.mjs";

const form = document.querySelector("#task-form");
const input = document.querySelector("#task-text");
const list = document.querySelector("#tasks");
const error = document.querySelector("#error");
const announcement = document.querySelector("#announcement");
let tasks = [];
let storage;
let readable = false;

function showError(message) {
  error.textContent = message;
  error.hidden = !message;
}

function render() {
  list.replaceChildren();
  for (const task of tasks) {
    const row = document.createElement("li");
    row.className = task.completed ? "task-row is-complete" : "task-row";
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.id = `task-${task.id}`;
    checkbox.checked = task.completed;
    checkbox.disabled = !readable;
    const label = document.createElement("label");
    label.htmlFor = checkbox.id;
    label.textContent = task.text;
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "delete-task";
    remove.textContent = "×";
    remove.setAttribute("aria-label", `Delete task: ${task.text}`);
    remove.disabled = !readable;
    checkbox.addEventListener("change", () => commit(toggleTask(tasks, task.id),
      task.completed ? "Task marked active." : "Task completed.", checkbox.id));
    remove.addEventListener("click", () => commit(deleteTask(tasks, task.id), "Task deleted.", "task-text"));
    row.append(checkbox, label, remove);
    list.append(row);
  }
  const completed = tasks.filter(task => task.completed).length;
  const remaining = tasks.length - completed;
  document.querySelector("#remaining").textContent = `${remaining} ${remaining === 1 ? "task" : "tasks"} left`;
  document.querySelector("#completion").textContent = tasks.length
    ? `${completed} of ${tasks.length} complete${remaining === 0 ? " — nicely done." : ""}`
    : "Nothing on your list yet";
  document.querySelector("#empty").hidden = tasks.length > 0;
  document.querySelector(".local-label").textContent = readable ? "Saved in this browser" : "Storage unavailable";
  input.disabled = !readable;
  form.querySelector("button").disabled = !readable;
}

// Only a successful browser-storage write advances visible state. A failed
// save must not pretend the task will survive reload or destroy the old list.
function commit(next, message, focusId) {
  try {
    storage.setItem(STORAGE_KEY, encodeTasks(next));
  } catch {
    showError("Your change could not be saved. The list is unchanged. Check browser storage and try again.");
    render();
    document.getElementById(focusId)?.focus();
    return false;
  }
  tasks = next;
  showError("");
  render();
  announcement.textContent = message;
  document.getElementById(focusId)?.focus();
  return true;
}

input.addEventListener("input", () => input.setCustomValidity(""));
form.addEventListener("submit", event => {
  event.preventDefault();
  if (!readable) return;
  try {
    const next = addTask(tasks, input.value, crypto.randomUUID());
    if (commit(next, "Task added.", "task-text")) input.value = "";
  } catch (failure) {
    input.setCustomValidity(failure.message);
    input.reportValidity();
  }
});

function readSavedList() {
  try {
    storage = window.localStorage;
    tasks = decodeTasks(storage.getItem(STORAGE_KEY));
    readable = true;
    showError("");
  } catch {
    readable = false;
    showError("Saved tasks could not be read. Editing is paused to keep your saved data unchanged.");
  }
  render();
}

window.addEventListener("storage", event => {
  if (event.storageArea === storage && (event.key === STORAGE_KEY || event.key === null)) {
    readSavedList();
    announcement.textContent = "List updated from another tab.";
  }
});
readSavedList();
