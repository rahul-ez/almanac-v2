import {describe,it,expect} from 'vitest';
import {readFileSync} from 'node:fs';
import {liveAnswer,liveCard,livePayload,createLiveAdapter} from '../../src/api/live';
import {answerSchema,cardSchema,userSchema} from '../../src/api/schemas';
const fixture=(name:string)=>JSON.parse(readFileSync(new URL('../../../contracts/'+name,import.meta.url),'utf8'));
describe('implemented backend integration boundary',()=>{
 it('validates actual backend answer fixtures in UI form',()=>{
  for(const name of ['event-answer','room-answer','office-hours-answer','no-matches','missing-coverage','ambiguous-faculty','missing-room-interval','unsupported']) {
   expect(()=>answerSchema.parse(liveAnswer(fixture('fixtures/'+name+'.json')))).not.toThrow();
  }
 });
 it('converts event records separately from assistant cards',()=>{
  expect(()=>cardSchema.parse(liveCard(fixture('event-fixtures/event-view.json'),'event'))).not.toThrow();
 });
 it('whitelists write fields and translates eligibility',()=>{
  const value=livePayload('events',{id:'x',updated_at:'today',version:1,title:'Event',topic_ids:['ml'],eligibility_mode:'all_students',allowed_years:[]},false);
  expect(value).not.toHaveProperty('version');expect(value).not.toHaveProperty('id');
  expect(value.topic_id).toBe('ml');expect(value.eligibility_rules.mode).toBe('unrestricted');
 });
 it('unwraps real login envelopes and sends username',async()=>{
  let sent:any;
  const transport=createLiveAdapter(async(_path,init)=>{sent=JSON.parse(String(init?.body));return {user:{id:'a',username:'student-a',role:'student',session_expires_at:'2026-11-06T00:00:00Z'},csrf_token:'token'};});
  const result=userSchema.parse(await transport('/auth/login',{method:'POST',body:JSON.stringify({email:'student-a',password:'secret'})}));
  expect(sent.username).toBe('student-a');expect(sent).not.toHaveProperty('email');expect(result.name).toBe('student-a');
 });
 it('translates offset pagination without changing cursor resources',async()=>{
  let path='';const t=createLiveAdapter(async(p)=>{path=p;return {items:[],next_offset:24};});
  expect(await t('/conversations?limit=12&cursor=12')).toEqual({items:[],next_cursor:'24'});
  expect(path).toContain('offset=12');expect(path).not.toContain('cursor');
 });
});
