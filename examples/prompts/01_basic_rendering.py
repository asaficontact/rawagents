"""Basic rendering example."""

from rawagents.prompts import PromptManager

def main():
    # 1. Initialize manager pointing to templates directory
    manager = PromptManager("./examples/prompts/templates")
    
    # 2. Render a simple template
    prompt = manager.render(
        "01_basic.j2",
        name="Alfred",
        user_id="u_123",
        user_role="admin",
        task="Summarize daily logs"
    )
    
    print("--- Rendered Prompt ---")
    print(prompt)

if __name__ == "__main__":
    main()

