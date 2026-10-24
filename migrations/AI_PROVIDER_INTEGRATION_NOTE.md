# AI provider integration source marker

The AI assistant is implemented without a database migration. It reads existing analytics aggregates only when the user explicitly opts in and has full branch scope. No AI endpoint can write business records or execute model-supplied tools.
