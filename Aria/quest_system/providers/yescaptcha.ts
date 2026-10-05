import { fetch } from 'undici';
import { Constants } from '../constants';

type BaseResponse = {
	errorId: 0 | 1;
	errorCode?: string;
	errorDescription?: string;
	taskId: string;
};

type ProcessingTaskResult = BaseResponse & {
	status: 'processing';
};

type ReadyTaskResult<T extends object = object> = BaseResponse & {
	status: 'ready';
	solution: T;
};

type TaskResult<T extends object = object> =
	| ProcessingTaskResult
	| ReadyTaskResult<T>;

type HCaptchaTaskProxyless = {
	type: 'HCaptchaTaskProxyless';
	websiteURL: string;
	websiteKey: string;
	userAgent?: string;
	isInvisible?: boolean;
	rqdata?: string;
};

export type YesCaptchaTask = {
	type: string;
	[key: string]: unknown;
};

type ImageToTextTask = {
	type: 'ImageToTextTaskM1';
	body: string; // Base64 encoded image
};

type HCaptchaSolution = {
	gRecaptchaResponse: string;
	userAgent?: string;
	respKey?: string;
};

type ImageToTextSolution = {
	text: string;
};

export class YesCaptchaSolver {
	public static readonly baseUrl = 'https://api.yescaptcha.com';
	private apiKey: string;
	private headersDefault: Headers = new Headers({
		'User-Agent': Constants.USER_AGENT,
		'Content-Type': 'application/json',
	});

	constructor(apiKey: string) {
		this.apiKey = apiKey;
	}

	private createTask = async <TTask extends { type: string }>(
		task: TTask,
	): Promise<BaseResponse> => {
		const response = await fetch(YesCaptchaSolver.baseUrl + '/createTask', {
			body: JSON.stringify({
				clientKey: this.apiKey,
				task,
			}),
			method: 'POST',
			headers: this.headersDefault,
		}).then((res) => res.json() as Promise<BaseResponse>);

		if (response.errorId === 1) {
			throw new Error(
				`Error creating task: ${JSON.stringify(response, null, 2)}`,
			);
		}
		return response;
	};

	private poolTaskResult<T extends object = object>(
		taskId: string,
	): Promise<ReadyTaskResult<T>> {
		return new Promise<ReadyTaskResult<T>>(async (resolve, reject) => {
			const timeout = setTimeout(() => {
				reject(new Error('Timeout while waiting for task result'));
			}, 120_000);

			while (true) {
				const response = await fetch(
					YesCaptchaSolver.baseUrl + '/getTaskResult',
					{
						body: JSON.stringify({
							clientKey: this.apiKey,
							taskId,
						}),
						method: 'POST',
						headers: this.headersDefault,
					},
				).then((res) => res.json() as any as TaskResult<T>);

				if (response.errorId === 1) {
					clearTimeout(timeout);
					return reject(
						`Error getting task result: ${JSON.stringify(response, null, 2)}`,
					);
				}

				if (response.status === 'processing') {
					await new Promise((res) => setTimeout(res, 3000));
					continue;
				}

				clearTimeout(timeout);
				return resolve(response);
			}
		});
	}

	async imageCaptcha(imageBase64: string): Promise<ImageToTextSolution> {
		const task: ImageToTextTask = {
			type: 'ImageToTextTaskM1',
			body: imageBase64,
		};

		return this.solveTask<ImageToTextTask, ImageToTextSolution>(task);
	}

	async solveTask<
		TTask extends { type: string },
		TSolution extends object = object,
	>(
		task: TTask,
	): Promise<TSolution> {
		if (!task || typeof task.type !== 'string' || !task.type.trim()) {
			throw new Error("YesCaptcha task must include a non-empty 'type'");
		}
		const createResult = await this.createTask({ ...task });
		if (!createResult.taskId) {
			throw new Error('No task ID in captcha create response');
		}
		const result = await this.poolTaskResult<TSolution>(createResult.taskId);
		return result.solution;
	}

	async hcaptcha(
		sitekey: string,
		url: string,
		options?: Omit<
			HCaptchaTaskProxyless,
			'type' | 'websiteURL' | 'websiteKey'
		>,
	): Promise<HCaptchaSolution> {
		const task: HCaptchaTaskProxyless = {
			type: 'HCaptchaTaskProxyless',
			websiteURL: url,
			websiteKey: sitekey,
			isInvisible: options?.isInvisible,
			userAgent: options?.userAgent,
			rqdata: options?.rqdata,
		};

		return this.solveTask<HCaptchaTaskProxyless, HCaptchaSolution>(task);
	}
}
