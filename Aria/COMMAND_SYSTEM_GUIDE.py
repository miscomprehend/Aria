"""
ARIA COMMAND SYSTEM - 500+ COMMANDS GUIDE
========================================

This guide explains:
1. The ANSI text display issue and fix
2. How to use the new CommandEngine
3. Integration with the Discord bot
4. Building 100+ more custom commands
"""

# ═══════════════════════════════════════════════════════════════════════════
# PART 1: FIXING ANSI TEXT CORRUPTION
# ═══════════════════════════════════════════════════════════════════════════

"""
THE PROBLEM:
When ANSI codes are sent as plain text in Discord messages, they display as 
raw escape sequences like:
  [0m[1m[4m...
  
WHY THIS HAPPENS:
Discord doesn't render ANSI codes in normal messages. They only work inside 
codeblocks with the 'ansi' language tag.

THE SOLUTION:
Always wrap ANSI-formatted text in Discord codeblocks using formatter._block()

WRONG (BREAKS):
  msg = f"{fmt.BOLD}Text{fmt.RESET}"
  api.send_message(channel_id, msg)
  
  Result: Shows raw ANSI codes to user

CORRECT (WORKS):
  msg = fmt._block(f"{fmt.BOLD}Text{fmt.RESET}")
  api.send_message(channel_id, msg)
  
  Result: Shows formatted text properly

The _block() function wraps content in:
  > ```ansi
  > {content}
  > ```

This tells Discord to render ANSI codes properly.
"""

# ═══════════════════════════════════════════════════════════════════════════
# PART 2: FORMATTER FUNCTIONS (ALL ANSI-SAFE)
# ═══════════════════════════════════════════════════════════════════════════

"""
Use these formatter functions - they ALL output ANSI-safe text:

formatter.success(msg)           - Green checkmark message
formatter.error(msg)             - Red X message  
formatter.warning(msg)           - Yellow warning message
formatter.status_box(...)        - Status display box
formatter._block(text)           - Raw ANSI-wrapped codeblock
formatter.command_page(...)      - Formatted command list
formatter.layout(...)            - 3-part layout (header/body/footer)

All above functions handle codeblock wrapping automatically!

Example:
    # ✓ CORRECT - Safe ANSI rendering
    msg = formatter.success("Command executed!")
    api.send_message(channel_id, msg)
    
    # ✓ CORRECT - Using formatter functions
    lines = [("cmd_name", "description"), ("cmd2", "desc2")]
    msg = formatter.command_page("Commands", lines, "footer text")
    api.send_message(channel_id, msg)
    
    # ✗ WRONG - Raw ANSI codes expose
    msg = f"{fmt.BOLD}Bold text{fmt.RESET}"
    api.send_message(channel_id, msg)  # SHOWS RAW ANSI!
"""

# ═══════════════════════════════════════════════════════════════════════════
# PART 3: USING THE COMMAND ENGINE
# ═══════════════════════════════════════════════════════════════════════════

"""
The CommandEngine manages 500+ commands with proper organization and help.

BASIC USAGE:

1. Import and initialize:
    from command_engine import CommandEngine, setup_commands_500
    
    engine = CommandEngine(prefix=";")
    setup_commands_500(engine)

2. Register new commands:
    engine.register_command(
        category="utility",
        name="echo",
        description="Echo back text",
        aliases=["repeat"]
    )

3. Get help output (all ANSI-safe):
    # Show all categories
    msg = engine.help_all_categories()
    
    # Show specific category with pagination
    msg = engine.help_category("utility", page=1)
    
    # Get command info
    msg = engine.command_info("echo")
    
    # Generate command walls (auto-splits large lists)
    messages = engine.generate_command_wall()
    for msg_text in messages:
        api.send_message(channel_id, msg_text)

4. Send help wall (handles 2000 char limit):
    engine.send_help_wall(ctx, api_client)
"""

# ═══════════════════════════════════════════════════════════════════════════
# PART 4: INTEGRATION WITH DISCORD BOT
# ═══════════════════════════════════════════════════════════════════════════

"""
Quick integration in main.py:

    from command_integration import integrate_command_engine
    
    # After bot initialization:
    bot = DiscordBot(token, prefix=";")
    integration = integrate_command_engine(bot, bot.api, bot.prefix)
    
    # Now these commands work:
    # +help                    - Show all categories
    # +help <category>         - Show commands in category  
    # +helpwall                - Show all commands (auto-paginated)
    # +cmdinfo <command>       - Get command details
    # +categories              - List all categories
    # +bold <text>             - Format bold
    # +italic <text>           - Format italic
    # +reverse <text>          - Reverse text
    # +mock <text>             - Mock SpongeBob text
    # And 490+ more...

The integration automatically:
- Creates @bot.command decorators
- Ensures all output is ANSI-safe
- Handles pagination for large outputs
- Manages Discord's 2000 char limit
"""

# ═══════════════════════════════════════════════════════════════════════════
# PART 5: BUILDING YOUR OWN COMMANDS (500+ TEMPLATE)
# ═══════════════════════════════════════════════════════════════════════════

"""
Each command category already has 10-60 registered commands.

TO ADD YOUR OWN COMMANDS:

1. In command_engine.py, find the setup_commands_500() function
2. Add to the relevant category:

    # Example: Add to "utility" category
    engine.register_command("utility", "mycommand", "Does something cool")
    engine.register_command("utility", "another", "Does more stuff", 
                           aliases=["alt", "a"])

3. Then implement in command_integration.py:

    @self.bot.command(name="mycommand", aliases=["mycmd"])
    def cmd_mycommand(ctx, args):
        # Always wrap output in formatter functions for ANSI safety!
        text = " ".join(args) if args else "No args"
        
        # ✓ CORRECT - Safe rendering
        msg_text = formatter._block(
            f"{fmt.CYAN}Result:{fmt.RESET} {text}"
        )
        # or
        msg_text = formatter.status_box("My Command", {
            "Input": text,
            "Output": "processed"
        })
        
        self.api_client.send_message(ctx["channel_id"], msg_text)

COMMON PATTERNS:

Pattern 1: Simple text output
    msg_text = formatter.success("Operation completed!")
    
Pattern 2: Key-value pairs
    msg_text = formatter.status_box("Title", {
        "Key1": "Value1",
        "Key2": "Value2"
    })
    
Pattern 3: Command list
    lines = [
        ("cmd1", "description 1"),
        ("cmd2", "description 2"),
    ]
    msg_text = formatter.command_page("Commands", lines, "footer")
    
Pattern 4: Custom ANSI
    msg_text = formatter._block(
        f"{fmt.BOLD}{fmt.PURPLE}Title{fmt.RESET}\n"
        f"{fmt.CYAN}Content here{fmt.RESET}"
    )
"""

# ═══════════════════════════════════════════════════════════════════════════
# PART 6: COMMAND CATEGORIES (500+ BREAKDOWN)
# ═══════════════════════════════════════════════════════════════════════════

"""
Current command organization:

System & Control (30)
    help, stop, restart, ping, version, config, eval, etc.

Utility Tools (50)
    echo, reverse, upper, lower, base64, hash, uuid, calc, etc.

User Profile (40)
    profile, avatar, status, bio, hypesquad, badges, etc.

Message Management (60)
    purge, edit, react, snipe, pin, quote, link, etc.

Text Formatting (40)
    bold, italic, code, spoiler, rainbow, glitch, etc.

Search & Discovery (50)
    user search, google, youtube, weather, crypto, news, etc.

Guild & Channel (50)
    server info, roles, channels, members, permissions, etc.

Reactions & Emoji (40)
    autoreact, emoji create/delete, sticker management, etc.

Nitro & Boosting (35)
    nitro status, boost management, badges, perks, etc.

Media & Files (40)
    upload, download, compress, convert, filter, etc.

Network & API (40)
    API status, HTTP requests, webhooks, etc.

Advanced Features (60)
    scripting, plugins, hooks, macros, scheduling, cron, etc.

Developer Tools (50)
    code execution, debugging, profiling, testing, etc.

TOTAL: 515+ COMMANDS
"""

# ═══════════════════════════════════════════════════════════════════════════
# PART 7: IMPORTING FROM OTHER SELFBOTS (PATTERN ANALYSIS)
# ═══════════════════════════════════════════════════════════════════════════

"""
From aiko-chan-ai/Discord-Quest-Auto-Completion-Selfbot patterns:
- Event-driven command detection
- Automatic message handling
- Context-aware responses
- Auto-completion logic

From CuteAnimeGirl1337/selfbot patterns:
- Modular command structure
- Category-based organization
- Nested command support
- Help text generation

We've incorporated these patterns into:
1. CommandCategory class - organizes commands
2. CommandInfo metadata - stores command details
3. Engine.generate_command_wall() - auto-pagination
4. Hierarchical help system - category -> command -> details

TO REPLICATE MORE PATTERNS:
1. Study their command dispatcher
2. Adapt patterns to CommandEngine
3. Add new categories as needed
4. Register commands in setup_commands_500()
5. Implement in command_integration.py
"""

# ═══════════════════════════════════════════════════════════════════════════
# PART 8: TESTING ANSI FIX
# ═══════════════════════════════════════════════════════════════════════════

"""
Verify ANSI fixes work:

1. Run in terminal:
    cd /workspaces/Aria/Aria
    python -c "from command_engine import CommandEngine, setup_commands_500; \
               e = CommandEngine(); setup_commands_500(e); \
               print(e.help_category('system'))"

2. Should see formatted output with colors, not raw ANSI codes

3. Check formatter output:
    python -c "import formatter as fmt; \
               print(fmt.success('Test works!'))"
    
    Should output Discord-safe codeblock, not raw ANSI

4. In Discord (after integration):
    +help system
    
    Should show formatted, colored help text (not raw codes)
"""

print(__doc__)
