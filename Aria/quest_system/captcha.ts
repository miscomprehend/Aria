import { Constants } from './constants';
import { CaptchaDataFromRequest } from './interface';
import { YesCaptchaSolver } from './providers/yescaptcha';
import { Utils } from './utils';

let yesCaptchaClient: YesCaptchaSolver | null = null;

if (process.env.YES_CAPTCHA_API_KEY) {
	console.log('YesCaptcha API key found. Captcha solving is enabled.');
	yesCaptchaClient = new YesCaptchaSolver(process.env.YES_CAPTCHA_API_KEY);
}

export function solveCaptcha(data: CaptchaDataFromRequest): Promise<string> {
	if (!yesCaptchaClient) {
		console.error('Captcha solving not implemented: YesCaptcha client not initialized. Set YES_CAPTCHA_API_KEY environment variable.');
		return Promise.reject(new Error('Captcha solving not available. Please set YES_CAPTCHA_API_KEY environment variable.'));
	}
	
	return yesCaptchaClient
		.hcaptcha(data.captcha_sitekey, 'https://discord.com', {
			rqdata: data.captcha_rqdata,
			isInvisible: false,
			userAgent: Constants.USER_AGENT,
		})
		.then((result) => result.gRecaptchaResponse)
		.catch((error) => {
			console.error('Captcha solving failed:', error.message);
			throw error;
		});
}
