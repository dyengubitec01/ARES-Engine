import { Test, TestingModule } from '@nestjs/testing';
import { ResponseInterceptor } from './response.interceptor';
import { Reflector } from '@nestjs/core';
import { ExecutionContext, CallHandler } from '@nestjs/common';
import { of } from 'rxjs';
import { ResponseCode } from '../constants/response-codes';

describe('ResponseInterceptor', () => {
  let interceptor: ResponseInterceptor<any>;
  let reflector: Reflector;

  const mockExecutionContext = {
    switchToHttp: jest.fn().mockReturnThis(),
    getHandler: jest.fn(),
    getClass: jest.fn(),
    getArgs: jest.fn(),
    getArgByIndex: jest.fn(),
    switchToRpc: jest.fn(),
    switchToWs: jest.fn(),
    getType: jest.fn(),
  } as unknown as ExecutionContext;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [ResponseInterceptor, Reflector],
    }).compile();

    interceptor = module.get<ResponseInterceptor<any>>(ResponseInterceptor);
    reflector = module.get<Reflector>(Reflector);
  });

  it('should be defined', () => {
    expect(interceptor).toBeDefined();
  });

  it('should wrap response with success format', (done) => {
    const mockData = { id: '123', name: 'test' };
    const mockCallHandler: CallHandler = {
      handle: () => of(mockData),
    };

    jest.spyOn(reflector, 'get').mockReturnValue(undefined);

    interceptor
      .intercept(mockExecutionContext, mockCallHandler)
      .subscribe((result) => {
        expect(result).toEqual({
          success: true,
          code: ResponseCode.UNKNOWN,
          message: '알 수 없는 오류가 발생했습니다',
          data: mockData,
        });
        done();
      });
  });

  it('should use response code from decorator', (done) => {
    const mockData = { id: '123' };
    const mockCallHandler: CallHandler = {
      handle: () => of(mockData),
    };

    jest.spyOn(reflector, 'get').mockImplementation((key) => {
      if (key === 'responseCode') return ResponseCode.CHAT_SESSION_CREATED;
      if (key === 'responseMessage') return '채팅방이 생성되었습니다';
      return undefined;
    });

    interceptor
      .intercept(mockExecutionContext, mockCallHandler)
      .subscribe((result) => {
        expect(result).toEqual({
          success: true,
          code: ResponseCode.CHAT_SESSION_CREATED,
          message: '채팅방이 생성되었습니다',
          data: mockData,
        });
        done();
      });
  });

  it('should extract data from nested object', (done) => {
    const innerData = { id: '123' };
    const mockData = { data: innerData, message: 'Custom message' };
    const mockCallHandler: CallHandler = {
      handle: () => of(mockData),
    };

    jest.spyOn(reflector, 'get').mockImplementation((key) => {
      if (key === 'responseCode') return ResponseCode.DOC_LIST_SUCCESS;
      return undefined;
    });

    interceptor
      .intercept(mockExecutionContext, mockCallHandler)
      .subscribe((result) => {
        expect(result).toEqual({
          success: true,
          code: ResponseCode.DOC_LIST_SUCCESS,
          message: 'Custom message',
          data: innerData,
        });
        done();
      });
  });

  it('should skip wrapping for SSE endpoints', (done) => {
    const mockData = { event: 'test' };
    const mockCallHandler: CallHandler = {
      handle: () => of(mockData),
    };

    jest.spyOn(reflector, 'get').mockImplementation((key) => {
      if (key === 'sse') return true;
      return undefined;
    });

    interceptor
      .intercept(mockExecutionContext, mockCallHandler)
      .subscribe((result) => {
        expect(result).toEqual(mockData);
        done();
      });
  });
});
