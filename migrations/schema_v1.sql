
CREATE TABLE audits (
	actor_id VARCHAR(64) NOT NULL, 
	action VARCHAR(100) NOT NULL, 
	target_id VARCHAR(64) NOT NULL, 
	details JSON NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	id VARCHAR(64) NOT NULL, 
	organization_id VARCHAR(64) NOT NULL, 
	PRIMARY KEY (id)
)

;

CREATE TABLE cursors (
	key VARCHAR(100) NOT NULL, 
	value TEXT NOT NULL, 
	PRIMARY KEY (key)
)

;

CREATE TABLE customers (
	name VARCHAR(200) NOT NULL, 
	product_version VARCHAR(30), 
	id VARCHAR(64) NOT NULL, 
	organization_id VARCHAR(64) NOT NULL, 
	PRIMARY KEY (id)
)

;

CREATE TABLE jobs (
	task_key VARCHAR(200) NOT NULL, 
	kind VARCHAR(30) NOT NULL, 
	payload JSON NOT NULL, 
	status VARCHAR(30) NOT NULL, 
	attempts INTEGER NOT NULL, 
	run_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	error TEXT, 
	id VARCHAR(64) NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (task_key)
)

;

CREATE TABLE news_items (
	mode VARCHAR(20) NOT NULL, 
	source VARCHAR(50) NOT NULL, 
	guid TEXT NOT NULL, 
	canonical_url TEXT NOT NULL, 
	content_hash VARCHAR(64) NOT NULL, 
	title TEXT NOT NULL, 
	summary TEXT NOT NULL, 
	category VARCHAR(40) NOT NULL, 
	status VARCHAR(30) NOT NULL, 
	published_at TIMESTAMP WITH TIME ZONE, 
	collected_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	id VARCHAR(64) NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (mode, source, guid), 
	UNIQUE (mode, canonical_url), 
	UNIQUE (mode, content_hash)
)

;

CREATE TABLE organizations (
	name VARCHAR(200) NOT NULL, 
	index_version INTEGER NOT NULL, 
	id VARCHAR(64) NOT NULL, 
	PRIMARY KEY (id)
)

;

CREATE TABLE users (
	username VARCHAR(80) NOT NULL, 
	display_name VARCHAR(100) NOT NULL, 
	password_hash TEXT NOT NULL, 
	role VARCHAR(30) NOT NULL, 
	active BOOLEAN NOT NULL, 
	id VARCHAR(64) NOT NULL, 
	organization_id VARCHAR(64) NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (username)
)

;

CREATE TABLE assignments (
	user_id VARCHAR(64) NOT NULL, 
	customer_account_id VARCHAR(64) NOT NULL, 
	PRIMARY KEY (user_id, customer_account_id), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	FOREIGN KEY(customer_account_id) REFERENCES customers (id)
)

;

CREATE TABLE conversations (
	customer_account_id VARCHAR(64) NOT NULL, 
	title VARCHAR(200) NOT NULL, 
	product_version VARCHAR(30), 
	platform VARCHAR(30) NOT NULL, 
	status VARCHAR(30) NOT NULL, 
	id VARCHAR(64) NOT NULL, 
	organization_id VARCHAR(64) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(customer_account_id) REFERENCES customers (id)
)

;

CREATE TABLE knowledge (
	customer_account_id VARCHAR(64), 
	title VARCHAR(200) NOT NULL, 
	status VARCHAR(30) NOT NULL, 
	current_revision_id VARCHAR(64), 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	id VARCHAR(64) NOT NULL, 
	organization_id VARCHAR(64) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(customer_account_id) REFERENCES customers (id)
)

;

CREATE TABLE login_sessions (
	user_id VARCHAR(64) NOT NULL, 
	token_hash VARCHAR(64) NOT NULL, 
	csrf VARCHAR(128) NOT NULL, 
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	id VARCHAR(64) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	UNIQUE (token_hash)
)

;

CREATE TABLE platform_bindings (
	platform VARCHAR(30) NOT NULL, 
	platform_tenant VARCHAR(100) NOT NULL, 
	application_id VARCHAR(100) NOT NULL, 
	chat_id VARCHAR(100) NOT NULL, 
	customer_account_id VARCHAR(64) NOT NULL, 
	id VARCHAR(64) NOT NULL, 
	organization_id VARCHAR(64) NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (platform, platform_tenant, application_id, chat_id), 
	FOREIGN KEY(customer_account_id) REFERENCES customers (id)
)

;

CREATE TABLE sources (
	customer_account_id VARCHAR(64), 
	title VARCHAR(200) NOT NULL, 
	kind VARCHAR(30) NOT NULL, 
	content TEXT NOT NULL, 
	external_url TEXT, 
	external_allowed BOOLEAN NOT NULL, 
	active BOOLEAN NOT NULL, 
	provenance JSON NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	id VARCHAR(64) NOT NULL, 
	organization_id VARCHAR(64) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(customer_account_id) REFERENCES customers (id)
)

;

CREATE TABLE drafts (
	conversation_id VARCHAR(64) NOT NULL, 
	operator_id VARCHAR(64) NOT NULL, 
	question TEXT NOT NULL, 
	original JSON NOT NULL, 
	edited_answer TEXT NOT NULL, 
	revision INTEGER NOT NULL, 
	confirmed_hash VARCHAR(64), 
	mode VARCHAR(20) NOT NULL, 
	latency_ms INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	id VARCHAR(64) NOT NULL, 
	organization_id VARCHAR(64) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(conversation_id) REFERENCES conversations (id), 
	FOREIGN KEY(operator_id) REFERENCES users (id)
)

;

CREATE TABLE imported_messages (
	binding_id VARCHAR(64) NOT NULL, 
	message_id VARCHAR(100) NOT NULL, 
	source_id VARCHAR(64) NOT NULL, 
	sender VARCHAR(100) NOT NULL, 
	timestamp TIMESTAMP WITH TIME ZONE NOT NULL, 
	reply_to VARCHAR(100), 
	content TEXT NOT NULL, 
	id VARCHAR(64) NOT NULL, 
	organization_id VARCHAR(64) NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (binding_id, message_id), 
	FOREIGN KEY(binding_id) REFERENCES platform_bindings (id), 
	FOREIGN KEY(source_id) REFERENCES sources (id)
)

;

CREATE TABLE messages (
	conversation_id VARCHAR(64) NOT NULL, 
	sender VARCHAR(100) NOT NULL, 
	content TEXT NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	id VARCHAR(64) NOT NULL, 
	organization_id VARCHAR(64) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(conversation_id) REFERENCES conversations (id)
)

;

CREATE TABLE revisions (
	knowledge_id VARCHAR(64) NOT NULL, 
	source_id VARCHAR(64) NOT NULL, 
	content TEXT NOT NULL, 
	customer_account_id VARCHAR(64), 
	visibility VARCHAR(30) NOT NULL, 
	version_min VARCHAR(30) NOT NULL, 
	version_max VARCHAR(30) NOT NULL, 
	valid_until TIMESTAMP WITH TIME ZONE, 
	authority INTEGER NOT NULL, 
	topic VARCHAR(100) NOT NULL, 
	claim_key VARCHAR(100), 
	claim_value VARCHAR(200), 
	verification TEXT NOT NULL, 
	reviewed_by VARCHAR(64), 
	public_approved BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	id VARCHAR(64) NOT NULL, 
	organization_id VARCHAR(64) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(knowledge_id) REFERENCES knowledge (id), 
	FOREIGN KEY(source_id) REFERENCES sources (id), 
	FOREIGN KEY(customer_account_id) REFERENCES customers (id), 
	FOREIGN KEY(reviewed_by) REFERENCES users (id)
)

;

CREATE TABLE chunks (
	revision_id VARCHAR(64) NOT NULL, 
	text TEXT NOT NULL, 
	embedding VECTOR, 
	embedding_space TEXT, 
	id VARCHAR(64) NOT NULL, 
	organization_id VARCHAR(64) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(revision_id) REFERENCES revisions (id)
)

;

CREATE TABLE feedback (
	draft_id VARCHAR(64) NOT NULL, 
	operator_id VARCHAR(64) NOT NULL, 
	rating VARCHAR(30) NOT NULL, 
	note TEXT NOT NULL, 
	id VARCHAR(64) NOT NULL, 
	organization_id VARCHAR(64) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(draft_id) REFERENCES drafts (id), 
	FOREIGN KEY(operator_id) REFERENCES users (id)
)

;

CREATE TABLE handoffs (
	draft_id VARCHAR(64) NOT NULL, 
	conversation_id VARCHAR(64) NOT NULL, 
	operator_id VARCHAR(64) NOT NULL, 
	payload JSON NOT NULL, 
	status VARCHAR(30) NOT NULL, 
	id VARCHAR(64) NOT NULL, 
	organization_id VARCHAR(64) NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (draft_id), 
	FOREIGN KEY(draft_id) REFERENCES drafts (id), 
	FOREIGN KEY(conversation_id) REFERENCES conversations (id), 
	FOREIGN KEY(operator_id) REFERENCES users (id)
)

;

CREATE TABLE reply_actions (
	draft_id VARCHAR(64) NOT NULL, 
	conversation_id VARCHAR(64) NOT NULL, 
	operator_id VARCHAR(64) NOT NULL, 
	text_hash VARCHAR(64) NOT NULL, 
	text TEXT NOT NULL, 
	citations JSON NOT NULL, 
	status VARCHAR(30) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	id VARCHAR(64) NOT NULL, 
	organization_id VARCHAR(64) NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (draft_id, text_hash), 
	FOREIGN KEY(draft_id) REFERENCES drafts (id), 
	FOREIGN KEY(conversation_id) REFERENCES conversations (id), 
	FOREIGN KEY(operator_id) REFERENCES users (id)
)

;
CREATE INDEX ix_audits_organization_id ON audits (organization_id);
CREATE INDEX ix_customers_organization_id ON customers (organization_id);
CREATE INDEX ix_users_organization_id ON users (organization_id);
CREATE INDEX ix_conversations_customer_account_id ON conversations (customer_account_id);
CREATE INDEX ix_conversations_organization_id ON conversations (organization_id);
CREATE INDEX ix_knowledge_status ON knowledge (status);
CREATE INDEX ix_knowledge_organization_id ON knowledge (organization_id);
CREATE INDEX ix_knowledge_customer_account_id ON knowledge (customer_account_id);
CREATE INDEX ix_platform_bindings_organization_id ON platform_bindings (organization_id);
CREATE INDEX ix_sources_customer_account_id ON sources (customer_account_id);
CREATE INDEX ix_sources_organization_id ON sources (organization_id);
CREATE INDEX ix_drafts_organization_id ON drafts (organization_id);
CREATE INDEX ix_drafts_conversation_id ON drafts (conversation_id);
CREATE INDEX ix_imported_messages_organization_id ON imported_messages (organization_id);
CREATE INDEX ix_messages_conversation_id ON messages (conversation_id);
CREATE INDEX ix_messages_organization_id ON messages (organization_id);
CREATE INDEX ix_revisions_knowledge_id ON revisions (knowledge_id);
CREATE INDEX ix_revisions_organization_id ON revisions (organization_id);
CREATE INDEX ix_chunks_revision_id ON chunks (revision_id);
CREATE INDEX ix_chunks_organization_id ON chunks (organization_id);
CREATE INDEX ix_feedback_organization_id ON feedback (organization_id);
CREATE INDEX ix_handoffs_organization_id ON handoffs (organization_id);
CREATE INDEX ix_reply_actions_organization_id ON reply_actions (organization_id);