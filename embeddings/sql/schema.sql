CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE document_chunks (
    id SERIAL PRIMARY KEY,
    content TEXT,
    embedding VECTOR(1536),
    document_name TEXT
);
create index on document_chunks(document_name);


CREATE TABLE document_chunks_paginated (
    id SERIAL PRIMARY KEY,
    document_name TEXT,
    page_number INTEGER,
    content TEXT,
    embedding VECTOR(1536)
);
create index on document_chunks_paginated(document_name);

