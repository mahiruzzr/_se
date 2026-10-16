CREATE TABLE IF NOT EXISTS visits (
    id integer PRIMARY KEY CHECK (id = 1),
    count bigint NOT NULL DEFAULT 0,
    updated_at timestamptz NOT NULL DEFAULT now()
);

INSERT INTO visits (id, count)
VALUES (1, 0)
ON CONFLICT (id) DO NOTHING;

CREATE TABLE IF NOT EXISTS messages (
    id bigserial PRIMARY KEY,
    author text NOT NULL CHECK (char_length(author) BETWEEN 1 AND 50),
    content text NOT NULL CHECK (char_length(content) BETWEEN 1 AND 500),
    created_at timestamptz NOT NULL DEFAULT now()
);

INSERT INTO messages (author, content) VALUES
    ('系統管理員', '歡迎來到 Docker 微服務展示系統！'),
    ('nginx', '我是反向代理，所有請求都先經過我。'),
    ('postgres', '我是資料庫，資料存在具名資料卷裡，容器重啟也不會消失。');
