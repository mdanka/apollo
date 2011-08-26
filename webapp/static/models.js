// Backbone.js models

Screen = Backbone.Model.extend({
	defaults: {
		title: null,
		contents: null,
	},
});

Backend = Backbone.RelationalModel.extend();
Location = Backbone.RelationalModel.extend({
    urlRoot: '/api/v1/location/',
    relations: [{
        type: Backbone.HasOne,
        key: 'parent',
        relatedModel: 'Location'
    }]
});
IncidentForm = Backbone.RelationalModel.extend();
ChecklistForm = Backbone.RelationalModel.extend();

Connection = Backbone.RelationalModel.extend({
    relations: [{
        type: Backbone.HasOne,
        key: 'backend',
        relatedModel: 'Backend',
        includeInJSON: 'resource_uri',
        reverseRelation: {
            key: 'connection'
        }
    }]
});

Contact = Backbone.RelationalModel.extend({
    relations: [{
        type: Backbone.HasMany,
		key: 'connections',
		relatedModel: 'Connection',
		reverserRelation: {
			key: 'contacts'
		}
    },{
        type: Backbone.HasOne,
        key: 'supervisor',
        relatedModel: 'Contact',
        includeInJSON: 'resource_uri'
    },{
        type: Backbone.HasOne,
        key: 'location',
        relatedModel: 'Location',
        includeInJSON: 'resource_uri'
    }]
});

Message = Backbone.RelationalModel.extend({
    relations: [{
		type: Backbone.HasOne,
		key: 'connection',
		relatedModel: 'Connection',
		reverseRelation: {
			key: 'messages'
		}
	}, {
	    type: Backbone.HasOne,
	    key: 'contact',
	    relatedModel: 'Contact',
	    reverseRelation: {
	        key: 'messages'
	    }
	}]
});

Incident = Backbone.RelationalModel.extend({
	relations: [{
		type: Backbone.HasOne,
		key: 'form',
		relatedModel: 'IncidentForm',
		reverseRelation: {
			key: 'incidents'
		}
	},{
		type: Backbone.HasOne,
		key: 'location',
		relatedModel: 'Location',
		reverseRelation: {
			key: 'incidents'
		}
	}, {
		type: Backbone.HasOne,
		key: 'observer',
		relatedModel: 'Contact',
		reverseRelation: {
			key: 'incidents'
		}
	}, {
		type: Backbone.HasOne,
		key: 'response',
		relatedModel: 'IncidentResponse',
		reverserRelation: {
			key: 'incident'
		}
	}]
});
IncidentResponse = Backbone.RelationalModel.extend();

Checklist = Backbone.RelationalModel.extend({
	relations: [{
		type: Backbone.HasOne,
		key: 'form',
		relatedModel: 'ChecklistForm',
		reverseRelation: {
			key: 'checklists'
		}
	}, {
		type: Backbone.HasOne,
		key: 'location',
		relatedModel: 'Location',
		reverseRelation: {
			key: 'checklists'
		} 
	}, {
		type: Backbone.HasOne,
		key: 'observer',
		relatedModel: 'Contact',
		reverseRelation: {
			key: 'checklists'
		}	
	}, {
		type: Backbone.HasOne,
		key: 'response',
		relatedModel: 'ChecklistResponse',
		reverseRelation: {
			key: 'checklist'
		}
    }]
});
ChecklistResponse = Backbone.RelationalModel.extend();