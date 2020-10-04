register_user_schema = {
    "type": "object",
    "properties": {
        "username": {"type": "string"},
        "password": {"type": "string"},
        "email": {"type": "string"}
    },
    "required": ["username", "password", "email"]
}

login_user_schema = {
    "type": "object",
    "properties": {
        "username": {"type": "string"},
        "password": {"type": "string"}
    },
    "required": ["username", "password"]
}

update_email_schema = {
    "type": "object",
    "properties": {
        "email": {"type": "string"}
    },
    "required": ["email"]
}

add_book_schema = {
    "type": "object",
    "properties": {
        "book_title": {"type": "string"},
        "secret": {"type": "string"}
    },
    "required": ["book_title", "secret"]
}
