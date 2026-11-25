import {
  ExceptionFilter,
  Catch,
  ArgumentsHost,
  HttpException,
  HttpStatus,
  Logger,
} from '@nestjs/common';
import { Request, Response } from 'express';
import { BusinessException } from '../exceptions/business.exception';
import { ResponseCode } from '../constants/response-codes';

export interface ApiErrorResponse {
  success: boolean;
  code: string;
  message: string;
  error: {
    statusCode: number;
    details?: string;
  };
}

@Catch()
export class GlobalExceptionFilter implements ExceptionFilter {
  private readonly logger = new Logger(GlobalExceptionFilter.name);

  catch(exception: unknown, host: ArgumentsHost) {
    const ctx = host.switchToHttp();
    const response = ctx.getResponse<Response>();
    const request = ctx.getRequest<Request>();

    let status = HttpStatus.INTERNAL_SERVER_ERROR;
    let code: string = ResponseCode.INTERNAL_ERROR;
    let message = '내부 서버 오류가 발생했습니다';
    let details: string | undefined;

    if (exception instanceof BusinessException) {
      // Handle BusinessException with custom code
      status = exception.getStatus();
      code = exception.getCode();
      const exceptionResponse = exception.getResponse() as { message?: string };
      message = exceptionResponse.message || message;
    } else if (exception instanceof HttpException) {
      // Handle standard HttpException
      status = exception.getStatus();
      const exceptionResponse = exception.getResponse();

      if (typeof exceptionResponse === 'string') {
        message = exceptionResponse;
      } else if (typeof exceptionResponse === 'object') {
        const responseObj = exceptionResponse as Record<string, unknown>;
        message = (responseObj.message as string) || message;
        details = responseObj.error as string;
      }

      // Map HTTP status to default response codes
      code = this.mapStatusToCode(status);
    } else if (exception instanceof Error) {
      message = '내부 서버 오류가 발생했습니다';
      details = 'Internal Server Error';
      this.logger.error(
        `Unhandled exception: ${exception.message}`,
        exception.stack,
      );
    }

    const errorResponse: ApiErrorResponse = {
      success: false,
      code,
      message,
      error: {
        statusCode: status,
        ...(details && { details }),
      },
    };

    this.logger.warn(
      `[${request.method}] ${request.url} - ${status} - ${code}: ${message}`,
    );

    response.status(status).json(errorResponse);
  }

  private mapStatusToCode(status: number): string {
    switch (status) {
      case HttpStatus.UNAUTHORIZED:
        return ResponseCode.UNAUTHORIZED;
      case HttpStatus.FORBIDDEN:
        return ResponseCode.FORBIDDEN;
      case HttpStatus.BAD_REQUEST:
        return ResponseCode.VALIDATION_FAILED;
      default:
        return ResponseCode.INTERNAL_ERROR;
    }
  }
}
