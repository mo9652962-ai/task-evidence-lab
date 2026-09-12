-- Task Evidence Lab schema v4: FTS5-backed task search with safe maintenance triggers.
CREATE VIRTUAL TABLE IF NOT EXISTS tasks_fts
USING fts5(title, description, content='tasks', content_rowid='id');

CREATE TRIGGER IF NOT EXISTS tasks_ai AFTER INSERT ON tasks BEGIN
  INSERT INTO tasks_fts(rowid, title, description)
  VALUES (new.id, new.title, new.description);
END;

CREATE TRIGGER IF NOT EXISTS tasks_ad AFTER DELETE ON tasks BEGIN
  INSERT INTO tasks_fts(tasks_fts, rowid, title, description)
  VALUES ('delete', old.id, old.title, old.description);
END;

CREATE TRIGGER IF NOT EXISTS tasks_au AFTER UPDATE OF title, description ON tasks BEGIN
  INSERT INTO tasks_fts(tasks_fts, rowid, title, description)
  VALUES ('delete', old.id, old.title, old.description);
  INSERT INTO tasks_fts(rowid, title, description)
  VALUES (new.id, new.title, new.description);
END;

INSERT INTO tasks_fts(rowid, title, description)
SELECT tasks.id, tasks.title, tasks.description
FROM tasks
WHERE tasks.id NOT IN (SELECT rowid FROM tasks_fts);
