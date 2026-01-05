"""Using Pydantic models as tool arguments.

This example demonstrates how to use Pydantic models for complex, structured
tool inputs. The executor automatically validates the arguments against the model.
"""

import asyncio
from pydantic import BaseModel, Field
from rawagents.tools import tool, ToolExecutor
from rawagents.utils.types import ToolCall

# 1. Define complex input model
class Address(BaseModel):
    street: str
    city: str
    zip_code: str

class UserProfile(BaseModel):
    name: str
    age: int = Field(ge=0, le=120)
    address: Address
    tags: list[str] = []

# 2. Define tool using the model
@tool
def create_user(profile: UserProfile) -> str:
    """Create a new user profile in the system.
    
    :param profile: The full user profile data.
    """
    # 'profile' is automatically parsed into a UserProfile instance
    return f"Created user {profile.name} in {profile.address.city} with {len(profile.tags)} tags."

async def main():
    executor = ToolExecutor([create_user])
    
    # 3. Verify Schema Structure
    schemas = executor.get_schemas()
    print("--- Schema ---")
    # Note: Pydantic models generate nested JSON schemas
    print(f"Root param: {list(schemas[0]['function']['parameters']['properties'].keys())}")
    
    # 4. Execute with complex nested data
    print("\n--- Execution ---")
    arguments = {
        "profile": {
            "name": "Alice",
            "age": 30,
            "address": {
                "street": "123 Main St",
                "city": "Wonderland",
                "zip_code": "12345"
            },
            "tags": ["admin", "beta-tester"]
        }
    }
    
    call = ToolCall(id="call_1", name="create_user", arguments=arguments)
    result = await executor.execute(call)
    
    print(f"Result: {result.content}")
    
    # 5. Validation Error Example
    print("\n--- Validation Error ---")
    bad_args = {"profile": {"name": "Bob", "age": 150, "address": {}}} # Age > 120
    call_bad = ToolCall(id="call_2", name="create_user", arguments=bad_args)
    
    result_bad = await executor.execute(call_bad)
    print(f"Is Error: {result_bad.is_error}")
    print(f"Error Msg: {result_bad.content}")

if __name__ == "__main__":
    asyncio.run(main())

