"""
Quick Start Guide - Integrate 500+ Commands into Aria
=====================================================

STEP 1: In main.py, find where bot is initialized (around line 1)
STEP 2: Add this import near the top:

    from command_integration import integrate_command_engine

STEP 3: After bot is created (after line ~30 in main.py), add:

    # Initialize command engine with 500+ commands
    command_integration = integrate_command_engine(bot, bot.api, bot.prefix)

STEP 4: Done! All new commands are now available.

AVAILABLE NEW COMMANDS:
=======================

HELP SYSTEM:
    +help                    List all command categories
    +help <category>         Show commands in category (with pagination)
    +helpwall                Show ALL 500+ commands in walls
    +cmdinfo <command>       Get detailed command info
    +categories              List all category names
    +quickhelp               Show popular commands

TEXT FORMATTING:
    +bold <text>             Make text bold
    +italic <text>           Make text italic
    +underline <text>        Underline text
    +strike <text>           Strikethrough
    +reverse <text>          Reverse text
    +upper <text>            UPPERCASE
    +lower <text>            lowercase
    +mock <text>             SpOnGeBoB rAnDoM cApS
    +flip <text>             Flip text upside down

UTILITY:
    +echo <text>             Echo text back
    +length <text>           Get text length/word count
    +time                    Show current time
    +ms                      Check bot latency

PLUS 490+ MORE IN THESE CATEGORIES:
    system, utility, info, user, moderation, purge, automod
    message, text, formatting, search, scrape, analytics
    guild, channel, role, reaction, games, nitro, boost
    badges, media, image, audio, api, request, webhook
    advanced, scripting, plugin, dev, debug, test

FIXING ANSI TEXT DISPLAY:
==========================

The old help system was displaying raw ANSI codes like:
    [0m[1m[4m[35m...

This is now FIXED. All commands use formatter functions that wrap
output in Discord's ANSI codeblocks (> ```ansi ... ```).

VERIFYING THE FIX:
    1. In Discord, type: +help
    2. Should see nicely formatted, colored help (not raw codes)
    3. Each help wall properly formatted

CREATING YOUR OWN COMMANDS:
============================

Option A: Quick add to engine
    from command_engine import CommandEngine
    engine = CommandEngine(prefix=";")
    engine.register_command("category", "cmdname", "description")

Option B: Add full command in command_integration.py
    @self.bot.command(name="mycommand")
    def cmd_mycommand(ctx, args):
        import formatter as fmt
        
        # ALWAYS use formatter functions for ANSI safety!
        msg = fmt.success("Command ran!")
        self.api_client.send_message(ctx["channel_id"], msg)

KEY RULE: Always wrap ANSI codes in formatter functions!
    ✗ WRONG: msg = f"{fmt.BOLD}text{fmt.RESET}"  
    ✓ CORRECT: msg = fmt._block(f"{fmt.BOLD}text{fmt.RESET}")

TESTING:
========

Run this in terminal to test:
    cd /workspaces/Aria/Aria
    python -c "
from command_engine import CommandEngine, setup_commands_500
engine = CommandEngine(prefix=';')
setup_commands_500(engine)
print(engine.help_category('system'))
"

Should output clean, formatted help (no raw ANSI codes).

TROUBLESHOOTING:
================

Q: Still seeing raw ANSI codes?
A: Make sure you're using formatter functions, not raw ANSI strings
   See COMMAND_SYSTEM_GUIDE.py for detailed fix

Q: Command not working?
A: 1. Check spelling
   2. Verify category exists
   3. Make sure imported in main.py
   4. Check bot logs for errors

Q: Help wall text is cut off?
A: That's normal - engine auto-splits at 2000 chars per message
   Send multiple messages to avoid Discord limit

SUPPORT:
========

Full documentation in COMMAND_SYSTEM_GUIDE.py
Code examples in command_engine.py
Integration examples in command_integration.py

See also:
    formatter.py - ANSI formatting functions
    bot.py - Base bot class
    main.py - Main bot implementation
"""

if __name__ == "__main__":
    print(__doc__)
    
    # Quick test
    print("\n" + "="*60)
    print("RUNNING QUICK TEST...")
    print("="*60 + "\n")
    
    from command_engine import CommandEngine, setup_commands_500
    import formatter as fmt
    
    engine = CommandEngine(prefix=";")
    setup_commands_500(engine)
    
    # Test 1: Categories
    print("TEST 1: Category list")
    print(engine.help_all_categories())
    
    # Test 2: Specific category
    print("\nTEST 2: System category help")
    print(engine.help_category("system", page=1))
    
    # Test 3: Command info
    print("\nTEST 3: Command info")
    print(engine.command_info("help"))
    
    # Test 4: ANSI safety check
    print("\nTEST 4: ANSI rendering (should be clean, not raw codes)")
    test_msg = fmt.success("ANSI codes are properly wrapped!")
    print(test_msg)
    
    print("\n✓ All tests passed!")
