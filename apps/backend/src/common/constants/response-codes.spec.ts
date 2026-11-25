import {
  ResponseCode,
  ResponseMessage,
  getResponseMessage,
  isSuccessCode,
  isErrorCode,
  getCodeCategory,
} from './response-codes';

describe('ResponseCode', () => {
  describe('Code Format', () => {
    it('should have all codes starting with BKN', () => {
      Object.values(ResponseCode).forEach((code) => {
        expect(code).toMatch(/^BKN/);
      });
    });

    it('should have all codes with 8 characters (BKN + 5 digits)', () => {
      Object.values(ResponseCode).forEach((code) => {
        expect(code).toHaveLength(8);
      });
    });

    it('should have all codes with valid 5-digit suffix', () => {
      Object.values(ResponseCode).forEach((code) => {
        const suffix = code.slice(3);
        expect(suffix).toMatch(/^\d{5}$/);
      });
    });
  });

  describe('ResponseMessage', () => {
    it('should have a message for every response code', () => {
      Object.values(ResponseCode).forEach((code) => {
        expect(ResponseMessage[code]).toBeDefined();
        expect(typeof ResponseMessage[code]).toBe('string');
        expect(ResponseMessage[code].length).toBeGreaterThan(0);
      });
    });
  });

  describe('getResponseMessage', () => {
    it('should return correct message for known code', () => {
      expect(getResponseMessage(ResponseCode.AUTH_LOGIN_SUCCESS)).toBe(
        '로그인 성공',
      );
      expect(getResponseMessage(ResponseCode.DOC_NOT_FOUND)).toBe(
        '문서를 찾을 수 없습니다',
      );
    });

    it('should return unknown message for invalid code', () => {
      expect(getResponseMessage('BKN99999' as any)).toBe(
        '알 수 없는 오류가 발생했습니다',
      );
    });
  });

  describe('isSuccessCode', () => {
    it('should return true for success codes (00-19)', () => {
      expect(isSuccessCode('BKN01100')).toBe(true); // 00
      expect(isSuccessCode('BKN02101')).toBe(true); // 01
      expect(isSuccessCode('BKN04200')).toBe(true); // 00
    });

    it('should return false for error codes (20-79)', () => {
      expect(isSuccessCode('BKN01120')).toBe(false); // 20
      expect(isSuccessCode('BKN04220')).toBe(false); // 20
    });

    it('should return false for invalid format', () => {
      expect(isSuccessCode('INVALID')).toBe(false);
      expect(isSuccessCode('BKN123')).toBe(false);
    });
  });

  describe('isErrorCode', () => {
    it('should return true for error codes (20-79)', () => {
      expect(isErrorCode('BKN01120')).toBe(true); // 20
      expect(isErrorCode('BKN04221')).toBe(true); // 21
    });

    it('should return false for success codes (00-19)', () => {
      expect(isErrorCode('BKN01100')).toBe(false); // 00
      expect(isErrorCode('BKN02101')).toBe(false); // 01
    });

    it('should return false for invalid format', () => {
      expect(isErrorCode('INVALID')).toBe(false);
      expect(isErrorCode('BKN123')).toBe(false);
    });
  });

  describe('getCodeCategory', () => {
    it('should extract correct category', () => {
      expect(getCodeCategory('BKN01100')).toBe('01'); // Auth
      expect(getCodeCategory('BKN02100')).toBe('02'); // Chat
      expect(getCodeCategory('BKN03100')).toBe('03'); // Admin
      expect(getCodeCategory('BKN04100')).toBe('04'); // Document
      expect(getCodeCategory('BKN05100')).toBe('05'); // Embedding
      expect(getCodeCategory('BKN06100')).toBe('06'); // Event
      expect(getCodeCategory('BKN00000')).toBe('00'); // Common
    });

    it('should return 00 for invalid format', () => {
      expect(getCodeCategory('INVALID')).toBe('00');
      expect(getCodeCategory('BKN123')).toBe('00');
    });
  });

  describe('Code Categories', () => {
    it('should have Common codes starting with BKN00', () => {
      expect(ResponseCode.UNKNOWN).toMatch(/^BKN00/);
      expect(ResponseCode.INTERNAL_ERROR).toMatch(/^BKN00/);
    });

    it('should have Auth codes starting with BKN01', () => {
      expect(ResponseCode.AUTH_LOGIN_SUCCESS).toMatch(/^BKN01/);
      expect(ResponseCode.AUTH_LOGOUT_SUCCESS).toMatch(/^BKN01/);
    });

    it('should have Chat codes starting with BKN02', () => {
      expect(ResponseCode.CHAT_SESSION_CREATED).toMatch(/^BKN02/);
      expect(ResponseCode.CHAT_FEEDBACK_SUCCESS).toMatch(/^BKN02/);
    });

    it('should have Admin codes starting with BKN03', () => {
      expect(ResponseCode.ADMIN_USER_LIST_SUCCESS).toMatch(/^BKN03/);
      expect(ResponseCode.ADMIN_AUTHORITY_GRANTED).toMatch(/^BKN03/);
    });

    it('should have Document codes starting with BKN04', () => {
      expect(ResponseCode.DOC_UPLOAD_SESSION_CREATED).toMatch(/^BKN04/);
      expect(ResponseCode.DOC_DELETE_SUCCESS).toMatch(/^BKN04/);
    });

    it('should have Embedding codes starting with BKN05', () => {
      expect(ResponseCode.EMBED_REQUEST_ACCEPTED).toMatch(/^BKN05/);
    });

    it('should have Event codes starting with BKN06', () => {
      expect(ResponseCode.EVENT_SUBSCRIBE_SUCCESS).toMatch(/^BKN06/);
    });
  });
});
