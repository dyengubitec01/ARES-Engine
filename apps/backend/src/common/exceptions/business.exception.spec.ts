import { HttpStatus } from '@nestjs/common';
import { BusinessException } from './business.exception';
import { ResponseCode } from '../constants/response-codes';

describe('BusinessException', () => {
  it('should be defined', () => {
    const exception = new BusinessException(ResponseCode.DOC_NOT_FOUND);
    expect(exception).toBeDefined();
  });

  it('should have correct code', () => {
    const exception = new BusinessException(ResponseCode.DOC_NOT_FOUND);
    expect(exception.getCode()).toBe(ResponseCode.DOC_NOT_FOUND);
  });

  it('should use default message from ResponseMessage', () => {
    const exception = new BusinessException(ResponseCode.DOC_NOT_FOUND);
    const response = exception.getResponse() as {
      code: string;
      message: string;
    };
    expect(response.message).toBe('문서를 찾을 수 없습니다');
  });

  it('should use custom message when provided', () => {
    const customMessage = 'Custom error message';
    const exception = new BusinessException(
      ResponseCode.DOC_NOT_FOUND,
      customMessage,
    );
    const response = exception.getResponse() as {
      code: string;
      message: string;
    };
    expect(response.message).toBe(customMessage);
  });

  it('should default to BAD_REQUEST status', () => {
    const exception = new BusinessException(ResponseCode.DOC_NOT_FOUND);
    expect(exception.getStatus()).toBe(HttpStatus.BAD_REQUEST);
  });

  it('should accept custom HTTP status', () => {
    const exception = new BusinessException(
      ResponseCode.DOC_NOT_FOUND,
      undefined,
      HttpStatus.NOT_FOUND,
    );
    expect(exception.getStatus()).toBe(HttpStatus.NOT_FOUND);
  });

  it('should work with string code', () => {
    const exception = new BusinessException('BKN99999', 'Unknown code');
    expect(exception.getCode()).toBe('BKN99999');
  });
});
