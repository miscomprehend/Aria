import { Constants } from './constants';
import { CaptchaDataFromRequest } from './interface';
import { NoCaptchaSolver } from './providers/nocaptcha';
import { YesCaptchaSolver } from './providers/yescaptcha';

type CaptchaProvider = {
	name: 'NoCaptchaAI' | 'YesCaptcha';
	hcaptcha: (
		sitekey: string,
		url: string,
		options: {
			rqdata?: string;
			isInvisible?: boolean;
			userAgent?: string;
		},
	) => Promise<{ gRecaptchaResponse: string }>;
};
let captchaProvider: CaptchaProvider | null = null;

if (process.env.NOCAPTCHAAI_API_KEY) {
	console.log('NoCaptchaAI API key found. Captcha solving is enabled.');
	const client = new NoCaptchaSolver(process.env.NOCAPTCHAAI_API_KEY);
	captchaProvider = {
		name: 'NoCaptchaAI',
		hcaptcha: client.hcaptcha.bind(client),
	};
} else if (process.env.YES_CAPTCHA_API_KEY) {
	console.log('YesCaptcha API key found. Captcha solving is enabled.');
	const client = new YesCaptchaSolver(process.env.YES_CAPTCHA_API_KEY);
	captchaProvider = {
		name: 'YesCaptcha',
		hcaptcha: client.hcaptcha.bind(client),
	};
}

export function solveCaptcha(data: CaptchaDataFromRequest): Promise<string> {
	if (!captchaProvider) {
		console.error('Captcha solving not available: set NOCAPTCHAAI_API_KEY or YES_CAPTCHA_API_KEY environment variable.');
		return Promise.reject(
			new Error(
				'Captcha solving not available. Please set NOCAPTCHAAI_API_KEY or YES_CAPTCHA_API_KEY environment variable.',
			),
		);
	}
	
	return captchaProvider
		.hcaptcha(data.captcha_sitekey, 'https://discord.com', {
			rqdata: data.captcha_rqdata,
			isInvisible: false,
			userAgent: data.userAgent || Constants.USER_AGENT,
		})
		.then((result) => result.gRecaptchaResponse)
		.catch((error) => {
			console.error(`Captcha solving failed with ${captchaProvider?.name}:`, error.message);
			throw error;
		});
}
