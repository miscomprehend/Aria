import { Client, APIGatewayBotInfo, WebhooksAPI } from '@discordjs/core';
import { RequestInit } from 'undici';
import { REST, DefaultRestOptions, ResponseLike } from '@discordjs/rest';
import { WebSocketManager, WebSocketShard } from '@discordjs/ws';
import { GatewaySendPayload, GatewayOpcodes } from 'discord-api-types/v10';
import { QuestManager } from './questManager';
import { AllQuestsResponse } from './interface';
import { Constants } from './constants';
import { Utils } from './utils';

async function makeRequest(
	url: string,
	init: RequestInit,
): Promise<ResponseLike> {
	// console.log(`Making request to ${url} with method ${init.method}...`);
	if (init.headers) {
		init.headers = Utils.makeHeaders(init.headers as any);
	}
	return DefaultRestOptions.makeRequest(url, init);
}

const originalSend = WebSocketShard.prototype.send;
WebSocketShard.prototype.send = async function (payload: GatewaySendPayload) {
	if (payload.op === GatewayOpcodes.Identify) {
		payload.d = {
			token: payload.d.token,
			properties: {
				...Constants.Properties,
				is_fast_connect: false,
				gateway_connect_reasons: 'AppSkeleton',
			},
			capabilities: 0,
			presence: payload.d.presence,
			compress: payload.d.compress,
			client_state: {
				guild_versions: {},
			},
		} as any;
	}
	return originalSend.call(this, payload);
};

export class ClientQuest extends Client {
	public questManager: QuestManager | null = null;
	public websocketManager: WebSocketManager;
	public webhook: WebhooksAPI;
	#webhookId: string | null = null;
	#webhookToken: string | null = null;
	constructor(token: string) {
		if (!token) {
			throw new Error('Token is required to initialize the client.');
		}
		const rest = new REST({ version: '10', makeRequest }).setToken(token);
		rest.on('rateLimited', (info: any) => {
			console.warn(
				`\n[RateLimit]\n` +
					`  -> Route: ${info.method} ${info.route}\n` +
					`  -> Scope: ${info.scope}${info.global ? ' (Global)' : ''}\n` +
					`  -> Limit: ${info.limit} requests\n` +
					`  -> Retry after: ${info.retryAfter}ms (${(info.retryAfter / 1000).toFixed(2)}s)\n`,
			);
		});
		const gateway = new WebSocketManager({
			token: token,
			intents: 0,
			rest,
			readyTimeout: 120_000,
		});
		gateway.fetchGatewayInformation = (
			force?: boolean,
		): Promise<APIGatewayBotInfo> => {
			return Promise.resolve({
				url: 'wss://gateway.discord.gg',
				shards: 1,
				session_start_limit: {
					total: 1000,
					remaining: 1000,
					reset_after: 14400000,
					max_concurrency: 1,
				},
			});
		};
		super({ rest, gateway });
		this.websocketManager = gateway;
		this.webhook = new WebhooksAPI(rest);
		gateway.on('error', (error) => {
			console.error('[Gateway Error]', error);
		});
	}
	connect() {
		return Promise.allSettled([
			Utils.updateLatestBuildVersion(),
			this.setupWebhook(),
		]).then(() => this.websocketManager.connect()).catch((e) => {
			console.error('Error during client connection:', e.message);
			return this.sendWebhookMessage('Error during client connection: ' + e.message)
				.catch(webhookErr => {
					console.error('Failed to send webhook error message:', webhookErr.message);
				});
		});
	}
	destroy() {
		return this.websocketManager.destroy();
	}
	setupWebhook() {
		return Utils.extractWebhookInfo()
			.then((info) => {
				if (info) {
					this.#webhookId = info.id;
					this.#webhookToken = info.token;
					console.log('Webhook setup complete.');
				}
			})
			.catch((error) => {
				console.warn('Failed to setup webhook:', error.message);
			});
	}
	fetchQuests(fetchExcludedQuests = false) {
		return this.rest
			.get('/quests/@me')
			.then((response) =>
				QuestManager.fromResponse(
					this,
					response as AllQuestsResponse,
					fetchExcludedQuests,
				),
			)
			.then((manager) => {
				this.questManager = manager;
				return manager;
			})
			.catch((error) => {
				console.error('Failed to fetch quests:', error.message);
				throw error;
			});
	}
	sendWebhookMessage(content: string) {
		if (this.#webhookId && this.#webhookToken) {
			return this.webhook
				.execute(this.#webhookId, this.#webhookToken, {
					content,
				})
				.catch((error) => {
					console.error('Failed to send webhook message:', error.message);
				});
		}
		return Promise.resolve();
	}
	emitQuestCompleted(questId: string) {
		return this.sendWebhookMessage(
			`[Quest Completed!](https://discord.com/quests/${questId})`,
		);
	}
}
