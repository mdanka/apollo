describe('Submission model', function() {
    beforeEach(function() {
        // set up our submission.
        this.submission = new SubmissionModel({data: {aa: 0, ab: 1, ac: null, ad: undefined }});

        // set up the fake server
        this.server = sinon.fakeServer.create();

        // set up the server response
        this.server.respondWith("POST", this.submission.urlRoot,
            [200, {'Content-Type': 'text/plain'}, 'OK']);
    });

    afterEach(function() {
        // restore normalcy
        this.server.restore();
    });

    it('only data.ab should exist, and should be 1', function() {
        this.submission.save();

        var response = this.server.requests[0].requestBody;
        console.log(response);

        var data = JSON.parse(response).data;
        console.log(data);

        expect(data['aa']).toBe(0);
        expect(data['ab']).toBe(1);
        expect(data.ac).toBe(undefined);
        expect(data.ad).toBe(undefined);
    });
});