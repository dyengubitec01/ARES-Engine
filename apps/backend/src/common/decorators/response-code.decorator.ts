import { SetMetadata, applyDecorators } from '@nestjs/common';

export const RESPONSE_CODE_KEY = 'responseCode';
export const RESPONSE_MESSAGE_KEY = 'responseMessage';

/**
 * Decorator to set response code and message for API endpoints
 * @param code - Business response code (e.g., 'BKN02100')
 * @param message - Optional custom message (defaults to ResponseMessage mapping)
 */
export const ResponseCode = (code: string, message?: string) => {
  return applyDecorators(
    SetMetadata(RESPONSE_CODE_KEY, code),
    SetMetadata(RESPONSE_MESSAGE_KEY, message),
  );
};
