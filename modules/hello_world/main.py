from fastmcp import FastMCP

def register(mcp: FastMCP):
    """
    Реєструє інструменти модуля Hello World.
    """

    @mcp.tool(name="say_hello")
    def say_hello() -> str:
        """
        Returns a simple hello world message. 
        Use this tool to test if the server is responding or just to greet the user.
        """
        return "Hello from the hello_world module!"