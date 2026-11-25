import { HttpException, HttpStatus } from '@nestjs/common';
import {
  ResponseCodeType,
  getResponseMessage,
} from '../constants/response-codes';

/**
 * Custom business exception that includes response code
 * Use this for all business logic errors to ensure consistent error responses
 */
export class BusinessException extends HttpException {
  public readonly code: string;

  constructor(
    code: ResponseCodeType | string,
    message?: string,
    status: HttpStatus = HttpStatus.BAD_REQUEST,
  ) {
    const finalMessage =
      message || getResponseMessage(code as ResponseCodeType);
    super({ code, message: finalMessage }, status);
    this.code = code;
  }

  getCode(): string {
    return this.code;
  }
}
