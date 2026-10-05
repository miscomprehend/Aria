from enum import IntEnum, IntFlag


class GatewayOpcodes(IntEnum):
    Dispatch = 0
    Heartbeat = 1
    Identify = 2
    PresenceUpdate = 3
    VoiceStateUpdate = 4
    Resume = 6
    Reconnect = 7
    RequestGuildMembers = 8
    InvalidSession = 9
    Hello = 10
    HeartbeatAck = 11
    StreamCreate = 18
    StreamDelete = 19
    StreamSetPaused = 22


class GatewayIntentBits(IntFlag):
    Guilds = 1 << 0
    GuildMembers = 1 << 1
    GuildModeration = 1 << 2
    GuildExpressions = 1 << 3
    GuildIntegrations = 1 << 4
    GuildWebhooks = 1 << 5
    GuildInvites = 1 << 6
    GuildVoiceStates = 1 << 7
    GuildPresences = 1 << 8
    GuildMessages = 1 << 9
    GuildMessageReactions = 1 << 10
    GuildMessageTyping = 1 << 11
    DirectMessages = 1 << 12
    DirectMessageReactions = 1 << 13
    DirectMessageTyping = 1 << 14
    MessageContent = 1 << 15
    GuildScheduledEvents = 1 << 16
    AutoModerationConfiguration = 1 << 20
    AutoModerationExecution = 1 << 21


DEFAULT_GATEWAY_INTENTS = int(
    GatewayIntentBits.Guilds
    | GatewayIntentBits.GuildMembers
    | GatewayIntentBits.GuildModeration
    | GatewayIntentBits.GuildExpressions
    | GatewayIntentBits.GuildIntegrations
    | GatewayIntentBits.GuildWebhooks
    | GatewayIntentBits.GuildInvites
    | GatewayIntentBits.GuildVoiceStates
    | GatewayIntentBits.GuildPresences
    | GatewayIntentBits.GuildMessages
    | GatewayIntentBits.GuildMessageReactions
    | GatewayIntentBits.GuildMessageTyping
    | GatewayIntentBits.DirectMessages
    | GatewayIntentBits.DirectMessageReactions
    | GatewayIntentBits.DirectMessageTyping
    | GatewayIntentBits.MessageContent
    | GatewayIntentBits.GuildScheduledEvents
    | GatewayIntentBits.AutoModerationConfiguration
    | GatewayIntentBits.AutoModerationExecution
)


class ActivityType(IntEnum):
    Playing = 0
    Streaming = 1
    Listening = 2
    Watching = 3
    Custom = 4
    Competing = 5


class RelationshipType(IntEnum):
    None_ = 0
    Friend = 1
    Blocked = 2
    PendingIncoming = 3
    PendingOutgoing = 4
    Implicit = 5
    Suggestion = 6


class VoiceOpcodes(IntEnum):
    Identify = 0
    SelectProtocol = 1
    Ready = 2
    Heartbeat = 3
    SessionDescription = 4
    Speaking = 5
    HeartbeatAck = 6
    Resume = 7
    Hello = 8
    Resumed = 9
    ClientsConnect = 11
    ClientDisconnect = 13
    MediaSinkWants = 15
    VoiceBackendVersion = 16
    ChannelOptionsUpdate = 17
    ClientFlags = 18
    SpeedTest = 19
    Platform = 20
    SecureFramesPrepareProtocolTransition = 21
    SecureFramesExecuteTransition = 22