const state = {
  tasks: [],
  filter: "all",
};

const elements = {
  form: document.querySelector("#task-form"),
  input: document.querySelector("#task-title"),
  formError: document.querySelector("#form-error"),
  list: document.querySelector("#task-list"),
  emptyState: document.querySelector("#empty-state"),
  emptyTitle: document.querySelector("#empty-title"),
  emptyHint: document.querySelector("#empty-hint"),
  summary: document.querySelector("#summary"),
  countAll: document.querySelector("#count-all"),
  countActive: document.querySelector("#count-active"),
  countCompleted: document.querySelector("#count-completed"),
  toast: document.querySelector("#toast"),
};

let toastTimer;

async function api(path, options = {}) {
  const headers = options.body ? { "Content-Type": "application/json" } : undefined;
  const response = await fetch(path, { ...options, headers });

  if (!response.ok) {
    let message = "發生錯誤，請稍後再試";

    try {
      const body = await response.json();
      if (body && body.message) {
        message = body.message;
      }
    } catch {
      message = `請求失敗（${response.status}）`;
    }

    throw new Error(message);
  }

  if (response.status === 204) {
    return null;
  }

  return response.json();
}

async function loadTasks() {
  try {
    state.tasks = await api("/api/tasks");
    render();
  } catch (error) {
    showToast(error.message);
  }
}

function visibleTasks() {
  if (state.filter === "active") {
    return state.tasks.filter((task) => !task.completed);
  }

  if (state.filter === "completed") {
    return state.tasks.filter((task) => task.completed);
  }

  return state.tasks;
}

function updateCounts() {
  const total = state.tasks.length;
  const completed = state.tasks.filter((task) => task.completed).length;

  elements.countAll.textContent = String(total);
  elements.countActive.textContent = String(total - completed);
  elements.countCompleted.textContent = String(completed);

  if (total === 0) {
    elements.summary.textContent = "目前沒有任務";
  } else if (completed === total) {
    elements.summary.textContent = `共 ${total} 件，全部完成了`;
  } else {
    elements.summary.textContent = `共 ${total} 件，還有 ${total - completed} 件進行中`;
  }
}

function updateEmptyState(tasks) {
  elements.emptyState.hidden = tasks.length > 0;

  if (state.tasks.length === 0) {
    elements.emptyTitle.textContent = "清單還是空的";
    elements.emptyHint.textContent = "新增第一件想完成的事吧。";
    return;
  }

  if (state.filter === "active") {
    elements.emptyTitle.textContent = "沒有進行中的任務";
    elements.emptyHint.textContent = "太棒了，全部都完成了。";
    return;
  }

  elements.emptyTitle.textContent = "還沒有完成的任務";
  elements.emptyHint.textContent = "完成一件任務後，它會出現在這裡。";
}

function createTaskElement(task) {
  const item = document.createElement("li");
  item.className = task.completed ? "task is-completed" : "task";
  item.dataset.id = String(task.id);

  const checkbox = document.createElement("input");
  checkbox.type = "checkbox";
  checkbox.className = "task-checkbox";
  checkbox.checked = task.completed;
  checkbox.setAttribute(
    "aria-label",
    task.completed ? `將「${task.title}」標記為未完成` : `將「${task.title}」標記為已完成`,
  );
  checkbox.addEventListener("change", () => toggleTask(task));

  const title = document.createElement("span");
  title.className = "task-title";
  title.textContent = task.title;

  const remove = document.createElement("button");
  remove.type = "button";
  remove.className = "delete";
  remove.textContent = "刪除";
  remove.setAttribute("aria-label", `刪除「${task.title}」`);
  remove.addEventListener("click", () => deleteTask(task));

  item.append(checkbox, title, remove);
  return item;
}

function render() {
  const tasks = visibleTasks();
  const fragment = document.createDocumentFragment();

  for (const task of tasks) {
    fragment.append(createTaskElement(task));
  }

  elements.list.replaceChildren(fragment);
  updateCounts();
  updateEmptyState(tasks);
}

function showFormError(message) {
  elements.formError.textContent = message;
  elements.formError.hidden = false;
}

function clearFormError() {
  elements.formError.hidden = true;
  elements.formError.textContent = "";
}

function showToast(message) {
  elements.toast.textContent = message;
  elements.toast.hidden = false;

  window.clearTimeout(toastTimer);
  toastTimer = window.setTimeout(() => {
    elements.toast.hidden = true;
  }, 2400);
}

async function createTask(title) {
  if (!title) {
    showFormError("請先輸入任務名稱");
    elements.input.focus();
    return;
  }

  if (title.length > 120) {
    showFormError("任務名稱不可超過 120 個字");
    elements.input.focus();
    return;
  }

  try {
    const task = await api("/api/tasks", {
      method: "POST",
      body: JSON.stringify({ title }),
    });

    state.tasks.push(task);
    elements.input.value = "";
    elements.input.focus();
    render();
  } catch (error) {
    showFormError(error.message);
  }
}

async function toggleTask(task) {
  try {
    const updated = await api(`/api/tasks/${task.id}/toggle`, { method: "PATCH" });
    state.tasks = state.tasks.map((item) => (item.id === updated.id ? updated : item));
    render();
  } catch (error) {
    showToast(error.message);
    await loadTasks();
  }
}

async function deleteTask(task) {
  try {
    await api(`/api/tasks/${task.id}`, { method: "DELETE" });
    state.tasks = state.tasks.filter((item) => item.id !== task.id);
    render();
    showToast("任務已刪除");
  } catch (error) {
    showToast(error.message);
  }
}

elements.form.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearFormError();
  await createTask(elements.input.value.trim());
});

elements.input.addEventListener("input", clearFormError);

document.querySelectorAll("[data-filter]").forEach((button) => {
  button.addEventListener("click", () => {
    state.filter = button.dataset.filter;

    document.querySelectorAll("[data-filter]").forEach((candidate) => {
      const active = candidate === button;
      candidate.classList.toggle("is-active", active);
      candidate.setAttribute("aria-pressed", String(active));
    });

    render();
  });
});

loadTasks();
