# Enhanced Quest System

This is an enhanced quest system for Aria that integrates the TypeScript Auto-Quest code into a Python implementation. It combines the best features from both systems.

## Features

### From Auto-Quest (TypeScript)
- **Sophisticated class structure** with Quest and QuestManager classes
- **Better type definitions** using dataclasses
- **Enhanced header management** for Discord API requests
- **YesCaptcha integration** for solving hCaptchas
- **Proxy ticket support** for Discord Says activities
- **Constants management** with proper user agent spoofing

### From Aria (Python)
- **Quest auto-completion** with background threading
- **Smart progress sending** with platform detection
- **Reward claiming** with multiple endpoint fallbacks
- **Quest filtering** by state (available, enrolled, completed, etc.)
- **Progress tracking** for watch, play, and stream quests

## Architecture

### Core Modules

#### `constants.py`
- Discord API constants
- User agent strings (desktop and Android)
- Client properties for spoofing
- Super properties header generation

#### `interface.py`
- Type-safe dataclasses for quest data
- Full API response models
- Quest state enums
- From/to dictionary conversion methods

#### `quest.py`
- Wrapper around quest data
- Convenience methods for quest state checking
- Human-readable representations

#### `questManager.py`
- Collection manager for quests
- Filtering methods (available, active, claimable, etc.)
- Quest lookup and manipulation

#### `utils.py`
- Header generation for different platforms
- Activity referrer generation
- Progress payload extraction
- Quest type detection
- Display name extraction

#### `captcha.py`
- CaptchaSolver class for solving hCaptchas
- Integration with YesCaptcha provider
- Global solver instance management

#### `providers/yescaptcha.py`
- YesCaptcha API client
- Task creation and polling
- Support for hCaptcha and image captchas

## Usage

### Basic Integration

The enhanced quest system is integrated into Aria's main `quest.py` file. It maintains backward compatibility while adding new features.

```python
from Aria.quest import QuestSystem
from Aria.quest_system import QuestManager, Quest, Utils

# Quest system is initialized with API client
quest_system = QuestSystem(api_client)

# Fetch quests
quest_system.fetch_quests()

# Get summary
summary = quest_system.get_summary()
print(f"Active quests: {len(summary['completeable'])}")

# Start auto-completion
quest_system.start()

# Get enhanced quest objects
available = quest_system.get_available_quests()
for quest in available:
    print(f"Quest: {quest.config.messages.quest_name}")
    print(f"State: {quest.get_state()}")
```

### Using New Enhanced Methods

```python
# Get quest by ID
quest = quest_system.get_quest_by_id("quest_id_123")
if quest:
    print(f"Expired: {quest.is_expired()}")
    print(f"Completed: {quest.is_completed()}")

# Get all claimable quests
claimable = quest_system.get_claimable_quests()

# Get active quests
active = quest_system.get_active_quests()
```

### Using Utils Directly

```python
from Aria.quest_system import Utils

# Create headers for API requests
headers = Utils.make_headers(token, is_android=False)

# Get quest type
quest_type = Utils.get_task_type(quest_data)

# Get quest display name
name = Utils.get_quest_display_name(quest_data)

# Check if expired
is_expired = Utils.is_expired(iso_date_string)
```

### Using QuestManager

```python
from Aria.quest_system import QuestManager, AllQuestsResponse

# Create from API response
response_data = api.get("/quests/@me")
response = AllQuestsResponse.from_dict(response_data, user_id)
manager = QuestManager.from_response(response)

# Query quests
available = manager.get_available()
active = manager.get_active()
claimable = manager.get_claimable()

# Get specific quest
quest = manager.get("quest_id_123")
```

## API Endpoints

The quest system uses the following Discord API endpoints:

- `GET /quests/@me` - Fetch all quests
- `POST /quests/{quest_id}/enroll` - Enroll in quest
- `POST /quests/{quest_id}/video-progress` - Send video progress
- `POST /quests/{quest_id}/heartbeat` - Send play/stream heartbeat
- `POST /quests/{quest_id}/claim-reward` - Claim quest reward

## Header Management

The system automatically creates properly formatted headers for Discord API requests:

- **User-Agent**: Spoofed Discord client version
- **Authorization**: User token
- **X-Super-Properties**: Base64-encoded client properties
- **X-Discord-Locale**: Locale information
- **X-Discord-Timezone**: Timezone information
- **Sec-CH-UA**: Chrome/Chromium version headers
- **Sec-Fetch-***: Security headers

Platform-specific headers are automatically selected based on the quest type.

## Captcha Handling

If the `YES_CAPTCHA_API_KEY` environment variable is set:

```python
from Aria.quest_system import get_captcha_solver

solver = get_captcha_solver()
if solver.is_available():
    # Solve hCaptcha
    solution = await solver.solve_captcha(captcha_data)
```

## Configuration

### Environment Variables

- `YES_CAPTCHA_API_KEY` - YesCaptcha API key for automatic captcha solving

### Refresh Intervals

- Quest refresh: 5 minutes (configurable via `refresh_interval`)
- API rate limit: 30 seconds between fetches
- Auto-complete loop: 45-60 seconds per cycle

## Backward Compatibility

The enhanced quest system maintains full backward compatibility with existing Aria code:

- All original methods are preserved
- Raw quest dictionaries are still available in `quest_system.quests`
- Legacy filtering methods still work
- Auto-complete functionality is unchanged

## Migration Guide

### From Auto-Quest TypeScript

The following TypeScript features have been ported:

| Feature | TypeScript | Python |
|---------|-----------|--------|
| Quest data types | Interfaces | Dataclasses |
| Quest wrapper | Quest class | Quest class |
| Collection manager | QuestManager | QuestManager |
| Header management | Utils class | Utils class |
| Constants | Constants class | Constants class |
| Captcha solving | YesCaptchaSolver | YesCaptchaSolver |

### From Legacy Aria

All legacy methods are still available:

- `fetch_quests()` - Fetch quests from API
- `enroll()` - Enroll in quest
- `claim()` - Claim rewards
- `start()` / `stop()` - Auto-completion control
- `get_summary()` - Get quest summary

## Performance

The quest system is optimized for performance:

- Lazy loading of quest data
- Efficient filtering with generator expressions
- Minimal API calls with configurable refresh intervals
- Background threading for auto-completion
- Smart endpoint retry logic

## Troubleshooting

### Quests not fetching

1. Verify token is valid
2. Check API rate limits
3. Ensure proper headers with `Utils.make_headers()`

### Progress not sending

1. Check quest type detection in `_task_type()`
2. Verify platform detection in `_task_platforms()`
3. Check API response for endpoint compatibility

### Captcha errors

1. Verify `YES_CAPTCHA_API_KEY` is set
2. Check captcha solver is initialized
3. Ensure hCaptcha is properly decoded

## Related Files

- [/quest_legacy.py](../quest_legacy.py) - Original Aria quest.py implementation
- [/quest.py](../quest.py) - Enhanced quest.py with Auto-Quest integration
- Auto-Quest TypeScript sources in [/quest_system/](.)

## License

This implementation combines code from:
- Aria project
- Auto-Quest-DiscordV2 project (https://github.com/lfathh/Auto-Quest-DiscordV2)

Both are used under their respective licenses.
