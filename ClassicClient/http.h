/*
 * http.h
 * Claude Assistant for Classic Mac OS 7.5
 *
 * HTTP client utilities and MacTCP networking
 *
 * Think C 7.0 Compatible Code
 */

#ifndef HTTP_H
#define HTTP_H

#include <Types.h>
#include <MacTCP.h>

/* HTTP Response structure */
typedef struct {
    short statusCode;       /* HTTP status code (200, 404, etc) */
    Handle headers;         /* Response headers */
    Handle body;            /* Response body */
    long bodyLength;        /* Length of body */
} HTTPResponse;

/* TCP Stream buffer */
#define kTCPBufferSize  8192L
#define kMaxHTTPResponse 65536L  /* 64 KB max response */

/* HTTP request methods */
#define kHTTPMethodGET   0
#define kHTTPMethodPOST  1

/* Connection timeout in ticks (60 = 1 second) */
#define kConnectionTimeout  600    /* 10 seconds */
#define kReadTimeout        1800   /* 30 seconds */

/* Network error codes (in addition to MacTCP errors) */
#define kHTTPErrTimeout      -1001
#define kHTTPErrBadResponse  -1002
#define kHTTPErrNoMemory     -1003
#define kHTTPErrBadURL       -1004

/* Function prototypes */

/*
 * InitNetwork
 *
 * Initialize MacTCP driver
 * Call once at startup
 */
OSErr InitNetwork(void);

/*
 * HTTPRequest
 *
 * Send HTTP request and receive response
 *
 * method: kHTTPMethodGET or kHTTPMethodPOST
 * host: Server hostname or IP (e.g. "127.0.0.1")
 * port: Server port (e.g. 8080)
 * path: Request path (e.g. "/code")
 * body: Request body (for POST) or NULL (for GET)
 * response: Pointer to HTTPResponse structure (allocated by caller)
 *
 * Returns: noErr on success, error code on failure
 */
OSErr HTTPRequest(short method, char *host, short port, char *path,
                  char *body, HTTPResponse *response);

/*
 * HTTPGet
 *
 * Convenience wrapper for GET requests
 */
OSErr HTTPGet(char *host, short port, char *path, HTTPResponse *response);

/*
 * HTTPPost
 *
 * Convenience wrapper for POST requests with form data
 */
OSErr HTTPPost(char *host, short port, char *path, char *formData,
               HTTPResponse *response);

/*
 * ParseHTTPResponse
 *
 * Parse HTTP response into structure
 *
 * rawResponse: Raw HTTP response data (Handle)
 * response: Pointer to HTTPResponse structure
 *
 * Returns: noErr on success, kHTTPErrBadResponse on parse error
 */
OSErr ParseHTTPResponse(Handle rawResponse, HTTPResponse *response);

/*
 * DisposeHTTPResponse
 *
 * Free memory allocated for HTTPResponse
 */
void DisposeHTTPResponse(HTTPResponse *response);

/*
 * URLEncode
 *
 * URL-encode a string for use in query parameters or form data
 *
 * input: String to encode
 * output: Buffer for encoded string (must be at least 3x input length)
 *
 * Returns: Length of encoded string
 */
long URLEncode(char *input, char *output);

/*
 * ExtractJobID
 *
 * Extract job_id from JSON response
 *
 * json: JSON string (e.g. {"job_id": "abc123"})
 * jobID: Buffer for job ID (at least 64 bytes)
 *
 * Returns: true if found, false otherwise
 */
Boolean ExtractJobID(char *json, char *jobID);

/*
 * ExtractJSONString
 *
 * Extract string value from JSON
 *
 * json: JSON string
 * key: Key to find (e.g. "status", "answer")
 * value: Buffer for value (at least 256 bytes for status, 32KB for answer)
 *
 * Returns: true if found, false otherwise
 */
Boolean ExtractJSONString(char *json, char *key, char *value, long maxLen);

/*
 * ResolveDNS
 *
 * Resolve hostname to IP address
 *
 * hostname: Hostname to resolve
 * ipAddr: Pointer to receive IP address
 *
 * Returns: noErr on success, error code on failure
 */
OSErr ResolveDNS(char *hostname, unsigned long *ipAddr);

/*
 * IPAddrToString
 *
 * Convert IP address to dotted decimal string
 *
 * ipAddr: IP address (network byte order)
 * str: Output buffer (at least 16 bytes)
 */
void IPAddrToString(unsigned long ipAddr, char *str);

/*
 * StringToIPAddr
 *
 * Convert dotted decimal string to IP address
 *
 * str: IP address string (e.g. "127.0.0.1")
 * ipAddr: Pointer to receive IP address
 *
 * Returns: true on success, false on parse error
 */
Boolean StringToIPAddr(char *str, unsigned long *ipAddr);

#endif /* HTTP_H */
