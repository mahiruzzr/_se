use serde::Serialize;

pub const MAX_TITLE_CHARS: usize = 120;

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct Task {
    pub id: u64,
    pub title: String,
    pub completed: bool,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ValidationError {
    EmptyTitle,
    TitleTooLong,
}

impl ValidationError {
    pub fn code(self) -> &'static str {
        match self {
            Self::EmptyTitle => "empty_title",
            Self::TitleTooLong => "title_too_long",
        }
    }

    pub fn message(self) -> &'static str {
        match self {
            Self::EmptyTitle => "任務名稱不能為空",
            Self::TitleTooLong => "任務名稱不可超過 120 個字",
        }
    }
}

#[derive(Debug)]
pub struct Store {
    tasks: Vec<Task>,
    next_id: u64,
}

impl Default for Store {
    fn default() -> Self {
        Self::new()
    }
}

impl Store {
    pub fn new() -> Self {
        Self {
            tasks: Vec::new(),
            next_id: 1,
        }
    }

    pub fn list(&self) -> Vec<Task> {
        self.tasks.clone()
    }

    pub fn create(&mut self, raw_title: &str) -> Result<Task, ValidationError> {
        let title = raw_title.trim();

        if title.is_empty() {
            return Err(ValidationError::EmptyTitle);
        }

        if title.chars().count() > MAX_TITLE_CHARS {
            return Err(ValidationError::TitleTooLong);
        }

        let task = Task {
            id: self.next_id,
            title: title.to_string(),
            completed: false,
        };

        self.next_id += 1;
        self.tasks.push(task.clone());

        Ok(task)
    }

    pub fn toggle(&mut self, id: u64) -> Option<Task> {
        let task = self.tasks.iter_mut().find(|task| task.id == id)?;
        task.completed = !task.completed;
        Some(task.clone())
    }

    pub fn delete(&mut self, id: u64) -> bool {
        let previous_len = self.tasks.len();
        self.tasks.retain(|task| task.id != id);
        self.tasks.len() != previous_len
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn new_store_is_empty() {
        let store = Store::new();
        assert!(store.list().is_empty());
    }

    #[test]
    fn creates_task_with_trimmed_title_and_incrementing_id() {
        let mut store = Store::new();

        let first = store.create("  買牛奶  ").unwrap();
        let second = store.create("寫週報").unwrap();

        assert_eq!(first.id, 1);
        assert_eq!(first.title, "買牛奶");
        assert!(!first.completed);
        assert_eq!(second.id, 2);
        assert_eq!(store.list().len(), 2);
    }

    #[test]
    fn rejects_empty_and_whitespace_only_titles() {
        let mut store = Store::new();

        assert_eq!(store.create(""), Err(ValidationError::EmptyTitle));
        assert_eq!(store.create(" \t\n　 "), Err(ValidationError::EmptyTitle));
        assert!(store.list().is_empty());
    }

    #[test]
    fn accepts_title_with_exactly_max_length() {
        let mut store = Store::new();
        let title = "好".repeat(MAX_TITLE_CHARS);

        let task = store.create(&title).unwrap();

        assert_eq!(task.title.chars().count(), MAX_TITLE_CHARS);
    }

    #[test]
    fn rejects_title_longer_than_max_length() {
        let mut store = Store::new();
        let title = "好".repeat(MAX_TITLE_CHARS + 1);

        assert_eq!(store.create(&title), Err(ValidationError::TitleTooLong));
        assert!(store.list().is_empty());
    }

    #[test]
    fn toggles_completion_back_and_forth() {
        let mut store = Store::new();
        let task = store.create("重構 API").unwrap();

        let completed = store.toggle(task.id).unwrap();
        assert!(completed.completed);
        assert!(store.list()[0].completed);

        let reopened = store.toggle(task.id).unwrap();
        assert!(!reopened.completed);
        assert!(!store.list()[0].completed);
    }

    #[test]
    fn returns_none_or_false_for_unknown_ids() {
        let mut store = Store::new();

        assert_eq!(store.toggle(99), None);
        assert!(!store.delete(99));
    }

    #[test]
    fn deletes_only_the_requested_task() {
        let mut store = Store::new();
        let first = store.create("任務 A").unwrap();
        let second = store.create("任務 B").unwrap();

        assert!(store.delete(first.id));

        let remaining = store.list();
        assert_eq!(remaining.len(), 1);
        assert_eq!(remaining[0].id, second.id);
        assert!(!store.delete(first.id));
    }

    #[test]
    fn exposes_stable_error_codes_and_messages() {
        assert_eq!(ValidationError::EmptyTitle.code(), "empty_title");
        assert_eq!(
            ValidationError::TitleTooLong.message(),
            "任務名稱不可超過 120 個字"
        );
    }
}
