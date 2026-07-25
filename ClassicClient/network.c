/*
 * network.c
 * Claude Assistant for Classic Mac OS 7.5
 *
 * MacTCP HTTP client implementation
 *
 * Think C 7.0 Compatible Code
 */

#include "globals.h"
#include "http.h"
#include <String.h>
#include <Memory.h>
#include <OSUtils.h>

/* TCP stream globals */
static StreamPtr gTCPStream = NULL;
static Boolean gNetworkInitialized = false;

/* Forward declarations */
static OSErr OpenTCPConnection(char *host, short port, StreamPtr *stream);
static OSErr CloseTCPConnection(StreamPtr stream);
static OSErr SendTCPData(StreamPtr stream, char *data, long length);
static OSErr ReceiveTCPData(StreamPtr stream, Handle *data);
static void BuildHTTPRequest(short method, char *host, char *path, char *body, char *request);

/*
 * InitNetwork
 *
 * Initialize MacTCP driver
 */
OSErr InitNetwork(void)
{
    OSErr err;
    short tcpDriver;

    if (gNetworkInitialized) {
        return noErr;
    }

    /* Open MacTCP driver */
    err = OpenDriver("\p.IPP", &tcpDriver);
    if (err != noErr) {
        return err;
    }

    gNetworkInitialized = true;
    return noErr;
}

/*
 * HTTPRequest
 *
 * Send HTTP request and receive response
 */
OSErr HTTPRequest(short method, char *host, short port, char *path,
                  char *body, HTTPResponse *response)
{
    OSErr err;
    StreamPtr stream;
    char request[4096];
    Handle rawResponse;
    long startTime;

    /* Initialize network if needed */
    if (!gNetworkInitialized) {
        err = InitNetwork();
        if (err != noErr) {
            return err;
        }
    }

    /* Initialize response structure */
    response->statusCode = 0;
    response->headers = NULL;
    response->body = NULL;
    response->bodyLength = 0;

    /* Build HTTP request */
    BuildHTTPRequest(method, host, path, body, request);

    /* Open TCP connection */
    err = OpenTCPConnection(host, port, &stream);
    if (err != noErr) {
        return err;
    }

    /* Send request */
    err = SendTCPData(stream, request, strlen(request));
    if (err != noErr) {
        CloseTCPConnection(stream);
        return err;
    }

    /* Receive response */
    err = ReceiveTCPData(stream, &rawResponse);
    if (err != noErr) {
        CloseTCPConnection(stream);
        return err;
    }

    /* Close connection */
    CloseTCPConnection(stream);

    /* Parse response */
    err = ParseHTTPResponse(rawResponse, response);
    if (err != noErr) {
        DisposHandle(rawResponse);
        return err;
    }

    DisposHandle(rawResponse);
    return noErr;
}

/*
 * HTTPGet
 *
 * Convenience wrapper for GET requests
 */
OSErr HTTPGet(char *host, short port, char *path, HTTPResponse *response)
{
    return HTTPRequest(kHTTPMethodGET, host, port, path, NULL, response);
}

/*
 * HTTPPost
 *
 * Convenience wrapper for POST requests
 */
OSErr HTTPPost(char *host, short port, char *path, char *formData,
               HTTPResponse *response)
{
    return HTTPRequest(kHTTPMethodPOST, host, port, path, formData, response);
}

/*
 * OpenTCPConnection
 *
 * Open TCP connection to server
 */
static OSErr OpenTCPConnection(char *host, short port, StreamPtr *stream)
{
    OSErr err;
    TCPiopb pb;
    unsigned long ipAddr;
    long startTime;
    short i;

    /* Allocate TCP stream */
    *stream = (StreamPtr)NewPtr(sizeof(TCPStream));
    if (*stream == NULL) {
        return memFullErr;
    }

    /* Convert IP address string to numeric */
    if (!StringToIPAddr(host, &ipAddr)) {
        DisposPtr((Ptr)*stream);
        return kHTTPErrBadURL;
    }

    /* Create TCP stream */
    pb.ioCRefNum = 0;  /* Will be filled by MacTCP */
    pb.csCode = TCPCreate;
    pb.csParam.create.rcvBuff = NewPtr(kTCPBufferSize);
    pb.csParam.create.rcvBuffLen = kTCPBufferSize;
    pb.csParam.create.notifyProc = NULL;
    pb.csParam.create.userDataPtr = NULL;

    err = PBControl((ParmBlkPtr)&pb, false);
    if (err != noErr) {
        DisposPtr((Ptr)*stream);
        return err;
    }

    (*stream)->tcpStream = pb.tcpStream;

    /* Open active connection */
    pb.csCode = TCPActiveOpen;
    pb.tcpStream = (*stream)->tcpStream;
    pb.csParam.open.validityFlags = typeOfService | precedence;
    pb.csParam.open.ulpTimeoutValue = 60;  /* 60 seconds */
    pb.csParam.open.ulpTimeoutAction = 1;  /* Report timeout */
    pb.csParam.open.remoteHost = ipAddr;
    pb.csParam.open.remotePort = port;
    pb.csParam.open.localPort = 0;  /* Any port */
    pb.csParam.open.tosFlags = 0;
    pb.csParam.open.precedence = 0;
    pb.csParam.open.dontFrag = false;
    pb.csParam.open.timeToLive = 0;
    pb.csParam.open.security = 0;
    pb.csParam.open.optionCnt = 0;

    err = PBControl((ParmBlkPtr)&pb, false);
    if (err != noErr) {
        DisposPtr(pb.csParam.create.rcvBuff);
        DisposPtr((Ptr)*stream);
        return err;
    }

    /* Wait for connection to complete */
    startTime = TickCount();
    while (pb.csParam.open.connectionState != tcpEstablished) {
        /* Check timeout */
        if ((TickCount() - startTime) > kConnectionTimeout) {
            CloseTCPConnection(*stream);
            return kHTTPErrTimeout;
        }

        /* Yield to other processes */
        SystemTask();
    }

    return noErr;
}

/*
 * CloseTCPConnection
 *
 * Close TCP connection
 */
static OSErr CloseTCPConnection(StreamPtr stream)
{
    OSErr err;
    TCPiopb pb;

    if (stream == NULL) {
        return noErr;
    }

    /* Close connection */
    pb.csCode = TCPClose;
    pb.tcpStream = stream->tcpStream;
    pb.csParam.close.validityFlags = 0;
    pb.csParam.close.ulpTimeoutValue = 30;  /* 30 seconds */
    pb.csParam.close.ulpTimeoutAction = 1;  /* Report timeout */

    err = PBControl((ParmBlkPtr)&pb, false);

    /* Release connection */
    pb.csCode = TCPRelease;
    pb.tcpStream = stream->tcpStream;

    PBControl((ParmBlkPtr)&pb, false);

    /* Free stream */
    DisposPtr((Ptr)stream);

    return err;
}

/*
 * SendTCPData
 *
 * Send data over TCP connection
 */
static OSErr SendTCPData(StreamPtr stream, char *data, long length)
{
    OSErr err;
    TCPiopb pb;
    wdsEntry wds[2];

    /* Build WDS (Write Data Structure) */
    wds[0].length = length;
    wds[0].ptr = data;
    wds[1].length = 0;  /* Terminator */
    wds[1].ptr = NULL;

    /* Send data */
    pb.csCode = TCPSend;
    pb.tcpStream = stream->tcpStream;
    pb.csParam.send.validityFlags = 0;
    pb.csParam.send.ulpTimeoutValue = 60;
    pb.csParam.send.ulpTimeoutAction = 1;
    pb.csParam.send.pushFlag = true;  /* Send immediately */
    pb.csParam.send.urgentFlag = false;
    pb.csParam.send.wdsPtr = (Ptr)wds;

    err = PBControl((ParmBlkPtr)&pb, false);
    return err;
}

/*
 * ReceiveTCPData
 *
 * Receive data from TCP connection
 */
static OSErr ReceiveTCPData(StreamPtr stream, Handle *data)
{
    OSErr err;
    TCPiopb pb;
    long startTime;
    long totalReceived;
    char buffer[kTCPBufferSize];
    short dataAvailable;

    /* Create handle for received data */
    *data = NewHandle(0);
    if (*data == NULL) {
        return memFullErr;
    }

    totalReceived = 0;
    startTime = TickCount();

    /* Receive data until connection closes or timeout */
    while (true) {
        /* Check how much data is available */
        pb.csCode = TCPStatus;
        pb.tcpStream = stream->tcpStream;

        err = PBControl((ParmBlkPtr)&pb, false);
        if (err != noErr) {
            DisposHandle(*data);
            return err;
        }

        dataAvailable = pb.csParam.status.amtUnreadData;

        if (dataAvailable > 0) {
            /* Read available data */
            pb.csCode = TCPRcv;
            pb.tcpStream = stream->tcpStream;
            pb.csParam.receive.rcvBuff = buffer;
            pb.csParam.receive.rcvBuffLen = (dataAvailable < kTCPBufferSize) ?
                                            dataAvailable : kTCPBufferSize;
            pb.csParam.receive.commandTimeoutValue = 30;
            pb.csParam.receive.markFlag = false;
            pb.csParam.receive.urgentFlag = false;

            err = PBControl((ParmBlkPtr)&pb, false);
            if (err != noErr && err != connectionClosing) {
                DisposHandle(*data);
                return err;
            }

            /* Append to handle */
            if (pb.csParam.receive.rcvBuffLen > 0) {
                SetHandleSize(*data, totalReceived + pb.csParam.receive.rcvBuffLen);
                if (MemError() != noErr) {
                    DisposHandle(*data);
                    return kHTTPErrNoMemory;
                }

                HLock(*data);
                BlockMove(buffer, *(*data) + totalReceived, pb.csParam.receive.rcvBuffLen);
                HUnlock(*data);

                totalReceived += pb.csParam.receive.rcvBuffLen;
            }

            /* Reset timeout */
            startTime = TickCount();
        }

        /* Check if connection is closing */
        if (pb.csParam.status.connectionState == tcpClosing ||
            pb.csParam.status.connectionState == tcpClosed) {
            break;
        }

        /* Check timeout */
        if ((TickCount() - startTime) > kReadTimeout) {
            if (totalReceived == 0) {
                DisposHandle(*data);
                return kHTTPErrTimeout;
            }
            break;  /* Got some data, return it */
        }

        /* Yield to other processes */
        SystemTask();
    }

    return noErr;
}

/*
 * BuildHTTPRequest
 *
 * Build HTTP request string
 */
static void BuildHTTPRequest(short method, char *host, char *path, char *body, char *request)
{
    char *methodStr;
    long bodyLen;

    methodStr = (method == kHTTPMethodGET) ? "GET" : "POST";
    bodyLen = (body != NULL) ? strlen(body) : 0;

    /* Build request line */
    sprintf(request, "%s %s HTTP/1.0\r\n", methodStr, path);

    /* Add headers */
    sprintf(request + strlen(request), "Host: %s\r\n", host);
    sprintf(request + strlen(request), "User-Agent: ClaudeAssistant/1.0 (Mac OS 7.5)\r\n");
    sprintf(request + strlen(request), "Accept: */*\r\n");
    sprintf(request + strlen(request), "Connection: close\r\n");

    /* Add Content-Type and Content-Length for POST */
    if (method == kHTTPMethodPOST && body != NULL) {
        sprintf(request + strlen(request),
                "Content-Type: application/x-www-form-urlencoded\r\n");
        sprintf(request + strlen(request), "Content-Length: %ld\r\n", bodyLen);
    }

    /* End of headers */
    strcat(request, "\r\n");

    /* Add body for POST */
    if (method == kHTTPMethodPOST && body != NULL) {
        strcat(request, body);
    }
}

/*
 * ParseHTTPResponse
 *
 * Parse HTTP response into structure
 */
OSErr ParseHTTPResponse(Handle rawResponse, HTTPResponse *response)
{
    char *data;
    char *headerEnd;
    long totalLen;
    long headerLen;
    char statusLine[256];
    short i;

    if (rawResponse == NULL || *rawResponse == NULL) {
        return kHTTPErrBadResponse;
    }

    totalLen = GetHandleSize(rawResponse);
    if (totalLen == 0) {
        return kHTTPErrBadResponse;
    }

    HLock(rawResponse);
    data = *rawResponse;

    /* Find end of headers (empty line) */
    headerEnd = strstr(data, "\r\n\r\n");
    if (headerEnd == NULL) {
        headerEnd = strstr(data, "\n\n");
        if (headerEnd == NULL) {
            HUnlock(rawResponse);
            return kHTTPErrBadResponse;
        }
        headerEnd += 2;
    } else {
        headerEnd += 4;
    }

    headerLen = headerEnd - data;

    /* Extract status code from first line */
    i = 0;
    while (i < 255 && data[i] != '\r' && data[i] != '\n' && i < totalLen) {
        statusLine[i] = data[i];
        i++;
    }
    statusLine[i] = '\0';

    /* Parse status code (e.g. "HTTP/1.0 200 OK") */
    response->statusCode = 0;
    if (strstr(statusLine, "HTTP/") != NULL) {
        char *codeStart = strchr(statusLine, ' ');
        if (codeStart != NULL) {
            response->statusCode = atoi(codeStart + 1);
        }
    }

    /* Copy headers */
    response->headers = NewHandle(headerLen);
    if (response->headers != NULL) {
        HLock(response->headers);
        BlockMove(data, *response->headers, headerLen);
        HUnlock(response->headers);
    }

    /* Copy body */
    response->bodyLength = totalLen - headerLen;
    if (response->bodyLength > 0) {
        response->body = NewHandle(response->bodyLength + 1);  /* +1 for null terminator */
        if (response->body != NULL) {
            HLock(response->body);
            BlockMove(headerEnd, *response->body, response->bodyLength);
            (*response->body)[response->bodyLength] = '\0';  /* Null terminate */
            HUnlock(response->body);
        }
    }

    HUnlock(rawResponse);
    return noErr;
}

/*
 * DisposeHTTPResponse
 *
 * Free memory allocated for HTTPResponse
 */
void DisposeHTTPResponse(HTTPResponse *response)
{
    if (response->headers != NULL) {
        DisposHandle(response->headers);
        response->headers = NULL;
    }
    if (response->body != NULL) {
        DisposHandle(response->body);
        response->body = NULL;
    }
    response->statusCode = 0;
    response->bodyLength = 0;
}

/*
 * URLEncode
 *
 * URL-encode a string
 */
long URLEncode(char *input, char *output)
{
    long inLen;
    long outPos;
    short i;
    unsigned char c;
    char hex[4];

    inLen = strlen(input);
    outPos = 0;

    for (i = 0; i < inLen; i++) {
        c = input[i];

        /* Check if character needs encoding */
        if ((c >= 'A' && c <= 'Z') ||
            (c >= 'a' && c <= 'z') ||
            (c >= '0' && c <= '9') ||
            c == '-' || c == '_' || c == '.' || c == '~') {
            /* Safe character, copy as-is */
            output[outPos++] = c;
        } else if (c == ' ') {
            /* Space becomes + */
            output[outPos++] = '+';
        } else {
            /* Encode as %XX */
            sprintf(hex, "%%%02X", c);
            output[outPos++] = hex[0];
            output[outPos++] = hex[1];
            output[outPos++] = hex[2];
        }
    }

    output[outPos] = '\0';
    return outPos;
}

/*
 * ExtractJobID
 *
 * Extract job_id from JSON response
 */
Boolean ExtractJobID(char *json, char *jobID)
{
    return ExtractJSONString(json, "job_id", jobID, 64);
}

/*
 * ExtractJSONString
 *
 * Extract string value from JSON (simple parser)
 */
Boolean ExtractJSONString(char *json, char *key, char *value, long maxLen)
{
    char searchKey[128];
    char *keyPos;
    char *valueStart;
    char *valueEnd;
    long valueLen;
    short i;

    /* Build search pattern: "key": " */
    sprintf(searchKey, "\"%s\":", key);

    /* Find key */
    keyPos = strstr(json, searchKey);
    if (keyPos == NULL) {
        return false;
    }

    /* Skip to value start (after ": and opening quote) */
    valueStart = keyPos + strlen(searchKey);
    while (*valueStart == ' ' || *valueStart == '\t') {
        valueStart++;
    }
    if (*valueStart != '"') {
        return false;  /* Expected opening quote */
    }
    valueStart++;  /* Skip opening quote */

    /* Find closing quote */
    valueEnd = valueStart;
    while (*valueEnd != '\0' && *valueEnd != '"') {
        if (*valueEnd == '\\') {
            valueEnd++;  /* Skip escaped character */
        }
        valueEnd++;
    }

    if (*valueEnd != '"') {
        return false;  /* No closing quote found */
    }

    /* Copy value */
    valueLen = valueEnd - valueStart;
    if (valueLen >= maxLen) {
        valueLen = maxLen - 1;
    }

    for (i = 0; i < valueLen; i++) {
        value[i] = valueStart[i];
    }
    value[valueLen] = '\0';

    return true;
}

/*
 * StringToIPAddr
 *
 * Convert dotted decimal string to IP address
 */
Boolean StringToIPAddr(char *str, unsigned long *ipAddr)
{
    unsigned long a, b, c, d;
    short count;

    /* Parse dotted decimal (e.g. "127.0.0.1") */
    count = sscanf(str, "%ld.%ld.%ld.%ld", &a, &b, &c, &d);

    if (count != 4 || a > 255 || b > 255 || c > 255 || d > 255) {
        return false;
    }

    /* Build IP address (network byte order) */
    *ipAddr = (a << 24) | (b << 16) | (c << 8) | d;

    return true;
}

/*
 * IPAddrToString
 *
 * Convert IP address to dotted decimal string
 */
void IPAddrToString(unsigned long ipAddr, char *str)
{
    sprintf(str, "%ld.%ld.%ld.%ld",
            (ipAddr >> 24) & 0xFF,
            (ipAddr >> 16) & 0xFF,
            (ipAddr >> 8) & 0xFF,
            ipAddr & 0xFF);
}

/*
 * ResolveDNS
 *
 * Resolve hostname to IP address
 * (Simplified - just handles IP addresses for now)
 */
OSErr ResolveDNS(char *hostname, unsigned long *ipAddr)
{
    /* For now, just try to parse as IP address */
    /* Full DNS resolution would require MacTCP DNR (Domain Name Resolver) */
    if (StringToIPAddr(hostname, ipAddr)) {
        return noErr;
    }

    return kHTTPErrBadURL;
}

/*
 * SendJobRequest
 *
 * Send job request to Claude server
 * Returns job_id in jobID parameter
 */
OSErr SendJobRequest(char *prompt, char *mode, char *jobID)
{
    OSErr err;
    HTTPResponse response;
    char formData[8192];
    char encodedPrompt[6144];
    char encodedMode[64];
    char serverIP[32];
    short serverPort;
    char endpoint[32];

    /* Get server settings from globals */
    strncpy(serverIP, (char*)&gServerIP[1], gServerIP[0]);
    serverIP[gServerIP[0]] = '\0';
    serverPort = gServerPort;

    /* URL-encode prompt and mode */
    URLEncode(prompt, encodedPrompt);
    URLEncode(mode, encodedMode);

    /* Build form data */
    sprintf(formData, "prompt=%s", encodedPrompt);

    /* Determine endpoint based on mode */
    sprintf(endpoint, "/%s", mode);

    /* Send POST request */
    err = HTTPPost(serverIP, serverPort, endpoint, formData, &response);
    if (err != noErr) {
        return err;
    }

    /* Check status code */
    if (response.statusCode != 200) {
        DisposeHTTPResponse(&response);
        return kHTTPErrBadResponse;
    }

    /* Extract job_id from JSON response */
    if (response.body != NULL) {
        HLock(response.body);
        if (!ExtractJobID(*response.body, jobID)) {
            HUnlock(response.body);
            DisposeHTTPResponse(&response);
            return kHTTPErrBadResponse;
        }
        HUnlock(response.body);
    } else {
        DisposeHTTPResponse(&response);
        return kHTTPErrBadResponse;
    }

    DisposeHTTPResponse(&response);
    return noErr;
}

/*
 * CheckJobStatus
 *
 * Check job status on server
 * Returns true in isDone if job is complete
 * Returns result in result handle if done
 */
OSErr CheckJobStatus(char *jobID, Boolean *isDone, Handle *result)
{
    OSErr err;
    HTTPResponse response;
    char path[256];
    char serverIP[32];
    short serverPort;
    char status[32];
    char answer[32768];

    /* Get server settings */
    strncpy(serverIP, (char*)&gServerIP[1], gServerIP[0]);
    serverIP[gServerIP[0]] = '\0';
    serverPort = gServerPort;

    /* Build request path */
    sprintf(path, "/result/%s", jobID);

    /* Send GET request */
    err = HTTPGet(serverIP, serverPort, path, &response);
    if (err != noErr) {
        return err;
    }

    /* Check status code */
    if (response.statusCode != 200) {
        DisposeHTTPResponse(&response);
        return kHTTPErrBadResponse;
    }

    /* Parse JSON response */
    *isDone = false;
    if (response.body != NULL) {
        HLock(response.body);

        /* Extract status field */
        if (ExtractJSONString(*response.body, "status", status, 32)) {
            if (strcmp(status, "done") == 0) {
                *isDone = true;

                /* Extract answer field */
                if (ExtractJSONString(*response.body, "answer", answer, 32768)) {
                    /* Create handle for result */
                    *result = NewHandle(strlen(answer) + 1);
                    if (*result != NULL) {
                        HLock(*result);
                        strcpy(**result, answer);
                        HUnlock(*result);
                    }
                }
            }
        }

        HUnlock(response.body);
    }

    DisposeHTTPResponse(&response);
    return noErr;
}

/*
 * GetTextFromTE
 *
 * Get text from TextEdit control
 * Allocates memory for text - caller must free
 */
OSErr GetTextFromTE(TEHandle te, char **text, long *length)
{
    Handle teText;
    long teLen;

    if (te == NULL) {
        return paramErr;
    }

    teText = TEGetText(te);
    teLen = (*te)->teLength;

    /* Allocate memory for text */
    *text = NewPtr(teLen + 1);
    if (*text == NULL) {
        return memFullErr;
    }

    /* Copy text */
    if (teLen > 0) {
        HLock(teText);
        BlockMove(*teText, *text, teLen);
        HUnlock(teText);
    }

    (*text)[teLen] = '\0';  /* Null terminate */
    *length = teLen;

    return noErr;
}

/*
 * SetTextInTE
 *
 * Set text in TextEdit control
 */
void SetTextInTE(TEHandle te, char *text, long length)
{
    if (te == NULL) {
        return;
    }

    /* Select all existing text */
    TESetSelect(0, (*te)->teLength, te);

    /* Delete existing text */
    TEDelete(te);

    /* Insert new text */
    if (length > 0 && text != NULL) {
        TEInsert(text, length, te);
    }

    /* Scroll to beginning */
    TESetSelect(0, 0, te);
}

/*
 * ClearTE
 *
 * Clear TextEdit control
 */
void ClearTE(TEHandle te)
{
    if (te == NULL) {
        return;
    }

    /* Select all */
    TESetSelect(0, (*te)->teLength, te);

    /* Delete */
    TEDelete(te);
}
