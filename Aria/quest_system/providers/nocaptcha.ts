import { fetch } from 'undici';

type BaseResponse = {
	errorId: number;
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

type HCaptchaSolution = {
	gRecaptchaResponse: string;
};

type CreateTaskResponse = BaseResponse;

export class NoCaptchaSolver {
	public static readonly baseUrl = 'https://api.nocaptchaai.com';
	private apiKey: string;
	private headersDefault: Headers = new Headers({
		'User-Agent':
			'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3',
		'Content-Type': 'application/json',
	});

	constructor(apiKey: string) {
		this.apiKey = apiKey;
	}

	private createTask = async (task: HCaptchaTaskProxyless): Promise<CreateTaskResponse> => {
		const response = await fetch(NoCaptchaSolver.baseUrl + '/createTask', {
			body: JSON.stringify({
				clientKey: this.apiKey,
				task,
			}),
			method: 'POST',
			headers: this.headersDefault,
		}).then((res) => res.json() as any as CreateTaskResponse);

		if (response.errorId) {
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
					NoCaptchaSolver.baseUrl + '/getTaskResult',
					{
						body: JSON.stringify({
							clientKey: this.apiKey,
							taskId,
						}),
						method: 'POST',
						headers: this.headersDefault,
					},
				).then((res) => res.json() as any as TaskResult<T>);

				if (response.errorId) {
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
				return resolve(response as ReadyTaskResult<T>);
			}
		});
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

		const createResult = await this.createTask(task);
		const taskId = createResult.taskId;

		const result = await this.poolTaskResult<HCaptchaSolution>(taskId);
		return result.solution;
	}
}
